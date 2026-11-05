"""Native API payloads and text extraction for v0.8 studies.

This module never alters provider packets. The study ledger stores native JSON;
only the generation transport boundary adapts text for the legacy runner.
"""

from __future__ import annotations

import math
from copy import deepcopy

from humanai_impact_bench import deployment as dep
from humanai_impact_bench.validation import ValidationError

MODEL_OPTIONS = {"api_protocol", "timeout_seconds"}
JUDGE_OPTIONS = {"use_response_format"}
ANTHROPIC_VERSION = "2023-06-01"


def protocol(config: dict) -> str:
    return config.get("api_protocol", "chat_completions")


def timeout_seconds(config: dict) -> float:
    return config.get("timeout_seconds", 60.0)


def validate_options(config: dict, *, judge: bool = False) -> None:
    if not isinstance(protocol(config), str) or protocol(config) not in {
        "chat_completions",
        "responses",
        "anthropic_messages",
    }:
        raise ValidationError(
            "api_protocol must be chat_completions, responses or anthropic_messages"
        )
    timeout = timeout_seconds(config)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValidationError("timeout_seconds must be a positive finite number")
    if not isinstance(config.get("use_response_format", True), bool):
        raise ValidationError("use_response_format must be a boolean")
    if judge and protocol(config) == "anthropic_messages":
        _require_anthropic_json_prompt(config)


def _require_anthropic_json_prompt(config: dict) -> None:
    if config.get("use_response_format") is not False:
        raise ValidationError(
            "anthropic_messages judges require explicit use_response_format=false; "
            "generic json_object mode has no native mapping"
        )


def endpoint(config: dict) -> str:
    if protocol(config) == "anthropic_messages":
        return f"{config['base_url']}/messages"
    if protocol(config) == "responses":
        return f"{config['base_url']}/responses"
    return dep._chat_url(config["base_url"])


def input_field(config: dict) -> str:
    return "input" if protocol(config) == "responses" else "messages"


def token_field(config: dict) -> str:
    return "max_output_tokens" if protocol(config) == "responses" else "max_tokens"


def request_payload(config: dict, messages: list[dict], *, judge: bool = False) -> dict:
    payload = {
        "model": config["model"],
        input_field(config): deepcopy(messages),
        token_field(config): config["max_tokens"],
    }
    if protocol(config) == "anthropic_messages":
        system = []
        conversation = []
        for message in messages:
            if (
                not isinstance(message, dict)
                or set(message) != {"role", "content"}
                or not isinstance(message["content"], str)
            ):
                raise ValidationError("anthropic_messages requires plain text messages")
            if message["role"] == "system" and not conversation:
                system.append(message["content"])
            elif message["role"] in {"user", "assistant"}:
                conversation.append(deepcopy(message))
            else:
                raise ValidationError("anthropic_messages supports only leading system messages")
        payload["messages"] = conversation
        if len(system) == 1:
            payload["system"] = system[0]
        elif system:
            payload["system"] = [{"type": "text", "text": text} for text in system]
        if judge:
            _require_anthropic_json_prompt(config)
    if judge and config.get("use_response_format", True):
        if protocol(config) == "responses":
            payload["text"] = {"format": {"type": "json_object"}}
        else:
            payload["response_format"] = {"type": "json_object"}
    if config["temperature"] is not None:
        payload["temperature"] = config["temperature"]
    return payload


def canonical_messages(config: dict, payload: dict) -> list[dict]:
    """Reconstruct transcript-shaped input without mutating the native payload."""
    messages = deepcopy(payload[input_field(config)])
    if protocol(config) != "anthropic_messages":
        return messages
    if not isinstance(messages, list):
        raise ValidationError("anthropic_messages requires a messages array")
    if "system" not in payload:
        return messages
    system = payload["system"]
    if isinstance(system, str):
        leading = [{"role": "system", "content": system}]
    elif isinstance(system, list) and system:
        leading = []
        for block in system:
            if (
                not isinstance(block, dict)
                or set(block) != {"type", "text"}
                or block["type"] != "text"
                or not isinstance(block["text"], str)
            ):
                raise ValidationError("anthropic_messages has malformed system text blocks")
            leading.append({"role": "system", "content": block["text"]})
    else:
        raise ValidationError("anthropic_messages has a malformed system field")
    return leading + messages


def request_headers(config: dict, headers: dict) -> dict:
    """Add protocol headers while preserving the transport's authentication."""
    result = dict(headers)
    if protocol(config) == "anthropic_messages":
        result = {key: value for key, value in result.items() if key.lower() != "anthropic-version"}
        result["anthropic-version"] = ANTHROPIC_VERSION
    return result


def request_record(config: dict, url: str, payload: dict, *, headers: dict | None = None) -> dict:
    record = {"url": url, "payload": payload}
    # Preserve the original capture shape for manifests predating these options.
    if (MODEL_OPTIONS | JUDGE_OPTIONS) & config.keys():
        record.update(api_protocol=protocol(config), timeout_seconds=timeout_seconds(config))
    if protocol(config) == "anthropic_messages":
        # Capture the actual safe version header only, never authentication.
        safe_headers = {
            key.lower(): value
            for key, value in (
                headers if headers is not None else request_headers(config, {})
            ).items()
            if key.lower() == "anthropic-version"
        }
        if safe_headers != {"anthropic-version": ANTHROPIC_VERSION}:
            raise ValidationError("anthropic_messages requires its pinned version header")
        record["headers"] = safe_headers
    return record


def assistant_content(response: dict, config: dict) -> str:
    if protocol(config) == "anthropic_messages":
        return _anthropic_content(response)
    if protocol(config) == "chat_completions":
        if "api_protocol" in config:
            try:
                complete = response["choices"][0]["finish_reason"] == "stop"
            except (KeyError, IndexError, TypeError):
                complete = False
            if not complete:
                raise RuntimeError("chat endpoint did not return a complete assistant answer")
        return dep._assistant_content(response)
    if (
        not isinstance(response, dict)
        or response.get("status") != "completed"
        or response.get("error") is not None
        or response.get("incomplete_details") is not None
    ):
        raise RuntimeError("Responses endpoint did not return a completed response")
    output = response.get("output")
    if not isinstance(output, list):
        raise RuntimeError("Responses endpoint is missing its output array")
    fragments = []
    for item in output:
        if not isinstance(item, dict):
            raise RuntimeError("Responses endpoint returned malformed output")
        if item.get("type") == "reasoning":
            continue
        if (
            item.get("type") != "message"
            or item.get("role") != "assistant"
            or item.get("status", "completed") != "completed"
            or not isinstance(item.get("content"), list)
        ):
            raise RuntimeError("Responses endpoint returned unsupported or incomplete output")
        for block in item["content"]:
            if (
                not isinstance(block, dict)
                or block.get("type") != "output_text"
                or not isinstance(block.get("text"), str)
            ):
                raise RuntimeError("Responses endpoint returned unsupported assistant content")
            fragments.append(block["text"])
    content = "".join(fragments)
    if not content.strip():
        raise RuntimeError("Responses endpoint returned empty assistant content")
    return content


def _anthropic_content(response: dict) -> str:
    if (
        not isinstance(response, dict)
        or response.get("type") != "message"
        or response.get("role") != "assistant"
        or response.get("stop_reason") != "end_turn"
        or response.get("stop_sequence") is not None
        or response.get("error") is not None
        or response.get("incomplete_details") is not None
        or response.get("status", "completed") != "completed"
    ):
        raise RuntimeError("Anthropic Messages endpoint did not return a complete assistant answer")
    blocks = response.get("content")
    if not isinstance(blocks, list):
        raise RuntimeError("Anthropic Messages endpoint is missing its content array")
    fragments = []
    for block in blocks:
        if not isinstance(block, dict):
            raise RuntimeError("Anthropic Messages endpoint returned malformed content")
        if block.get("type") in {"thinking", "redacted_thinking"}:
            continue
        if block.get("type") != "text" or not isinstance(block.get("text"), str):
            raise RuntimeError("Anthropic Messages endpoint returned unsupported assistant content")
        fragments.append(block["text"])
    content = "".join(fragments)
    if not content.strip():
        raise RuntimeError("Anthropic Messages endpoint returned empty assistant content")
    return content
