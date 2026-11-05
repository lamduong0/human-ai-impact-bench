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


def protocol(config: dict) -> str:
    return config.get("api_protocol", "chat_completions")


def timeout_seconds(config: dict) -> float:
    return config.get("timeout_seconds", 60.0)


def validate_options(config: dict) -> None:
    if not isinstance(protocol(config), str) or protocol(config) not in {
        "chat_completions",
        "responses",
    }:
        raise ValidationError("api_protocol must be chat_completions or responses")
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


def endpoint(config: dict) -> str:
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
    if judge and config.get("use_response_format", True):
        if protocol(config) == "responses":
            payload["text"] = {"format": {"type": "json_object"}}
        else:
            payload["response_format"] = {"type": "json_object"}
    if config["temperature"] is not None:
        payload["temperature"] = config["temperature"]
    return payload


def request_record(config: dict, url: str, payload: dict) -> dict:
    record = {"url": url, "payload": payload}
    # Preserve the original capture shape for manifests predating these options.
    if (MODEL_OPTIONS | JUDGE_OPTIONS) & config.keys():
        record.update(api_protocol=protocol(config), timeout_seconds=timeout_seconds(config))
    return record


def assistant_content(response: dict, config: dict) -> str:
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
