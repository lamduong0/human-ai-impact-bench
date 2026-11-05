from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench import api_protocols as api
from humanai_impact_bench.experiments import run_study, validate_study, validate_study_state
from humanai_impact_bench.validation import ValidationError
from tests.test_v08_experiments import fake_transport, study_manifest, write_inputs


def response_packet(text="A complete answer."):
    return {
        "id": "resp-provider-native",
        "object": "response",
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            },
        ],
        "usage": {"output_tokens": 12},
    }


def responses_config():
    return {**study_manifest()["judges"][0], "api_protocol": "responses"}


def test_native_payload_and_format_omission_are_explicit():
    config = responses_config()
    messages = [{"role": "user", "content": "Return JSON."}]
    assert api.endpoint(config) == "https://judge.example/v1/responses"
    assert api.request_payload(config, messages, judge=True) == {
        "model": "judge-1",
        "input": messages,
        "max_output_tokens": 64,
        "temperature": 0,
        "text": {"format": {"type": "json_object"}},
    }
    config.update(temperature=None, use_response_format=False)
    assert api.request_payload(config, messages, judge=True) == {
        "model": "judge-1",
        "input": messages,
        "max_output_tokens": 64,
    }


def test_output_text_extraction_ignores_reasoning_and_preserves_native_packet():
    packet = response_packet("First ")
    packet["output"][1]["content"].append({"type": "output_text", "text": "second."})
    original = deepcopy(packet)
    assert api.assistant_content(packet, responses_config()) == "First second."
    assert packet == original


@pytest.mark.parametrize(
    "change",
    [
        {"status": "incomplete"},
        {"status": "failed"},
        {"status": None},
        {"error": {"code": "failure"}},
        {"incomplete_details": {"reason": "max_output_tokens"}},
        {"output": []},
        {"output": [{"type": "reasoning", "summary": []}]},
        {"output": [{"type": "message", "role": "assistant", "content": []}]},
        {"output": "malformed"},
    ],
)
def test_incomplete_or_empty_responses_are_rejected(change):
    packet = response_packet()
    packet.update(change)
    with pytest.raises(RuntimeError):
        api.assistant_content(packet, responses_config())


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls", None])
def test_explicit_chat_protocol_requires_complete_answer(finish_reason):
    packet = {"choices": [{"message": {"content": "Partial"}, "finish_reason": finish_reason}]}
    config = study_manifest()["targets"][0]
    assert api.assistant_content(packet, config) == "Partial"
    with pytest.raises(RuntimeError):
        api.assistant_content(packet, {**config, "api_protocol": "chat_completions"})


@pytest.mark.parametrize(
    "group,settings",
    [
        ("targets", {"api_protocol": "unknown"}),
        ("targets", {"api_protocol": []}),
        ("targets", {"timeout_seconds": True}),
        ("targets", {"timeout_seconds": 0}),
        ("targets", {"timeout_seconds": float("inf")}),
        ("targets", {"use_response_format": False}),
        ("judges", {"use_response_format": "false"}),
    ],
)
def test_invalid_optional_config_is_rejected(group, settings):
    manifest = study_manifest()
    manifest[group][0].update(settings)
    with pytest.raises(ValidationError):
        validate_study(manifest)


@pytest.mark.parametrize(
    "target_protocol,judge_protocol",
    [
        ("responses", "chat_completions"),
        ("chat_completions", "responses"),
        ("responses", "responses"),
    ],
)
@pytest.mark.parametrize("use_format", [True, False])
def test_mixed_protocols_capture_native_packets_and_verify(
    tmp_path, scenario_factory, target_protocol, judge_protocol, use_format
):
    path, _ = write_inputs(tmp_path, scenario_factory)
    manifest = json.loads(path.read_text())
    for group, protocol in (("targets", target_protocol), ("judges", judge_protocol)):
        manifest[group][0].update(api_protocol=protocol, timeout_seconds=120, temperature=None)
    manifest["judges"][0]["use_response_format"] = use_format
    path.write_text(json.dumps(manifest))
    calls = []

    def transport(url, payload, headers, timeout):
        assert timeout == 120
        is_responses = url.endswith("/responses")
        is_judge = payload["model"].startswith("judge")
        assert "temperature" not in payload
        format_key = "text" if is_responses else "response_format"
        assert (format_key in payload) == (is_judge and use_format)
        messages = payload["input" if is_responses else "messages"]
        if is_judge:
            material = json.loads(messages[-1]["content"])
            text = json.dumps(
                {
                    "scores": dict.fromkeys(material["scenario"]["dimensions"], 4),
                    "critical_failures": [],
                    "rationale": "Useful and bounded.",
                }
            )
        else:
            text = "I can help while keeping the choice yours."
        packet = (
            response_packet(text)
            if is_responses
            else {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}
        )
        calls.append((deepcopy(payload), deepcopy(packet)))
        return packet

    root = tmp_path / "run"
    assert (
        run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)[
            "execution_status"
        ]
        == "complete"
    )
    checked = validate_study_state(root / "study.json", root)
    assert len(checked["rows"]) == 2
    captures = [
        capture
        for task in checked["tasks"]
        for attempt in task["attempts"]
        for capture in attempt["requests"]
    ]
    assert len(captures) == len(calls)
    for capture, (payload, packet) in zip(captures, calls, strict=True):
        request = json.loads((root / capture["request"]["path"]).read_text())
        assert request["payload"] == payload
        assert request["timeout_seconds"] == 120
        assert json.loads((root / capture["response"]["path"]).read_text()) == packet


@pytest.mark.parametrize("tamper", ["protocol", "timeout", "token_cap", "format", "output"])
def test_rehashed_native_packet_tampering_fails_verification(tmp_path, scenario_factory, tamper):
    path, _ = write_inputs(tmp_path, scenario_factory)
    manifest = json.loads(path.read_text())
    for group in ("targets", "judges"):
        manifest[group][0].update(api_protocol="responses", timeout_seconds=120)
    path.write_text(json.dumps(manifest))

    def transport(url, payload, headers, timeout):
        chat_payload = {
            "model": payload["model"],
            "messages": payload["input"],
            "max_tokens": payload["max_output_tokens"],
        }
        return response_packet(
            fake_transport(url, chat_payload, headers, timeout)["choices"][0]["message"]["content"]
        )

    root = tmp_path / "run"
    run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)
    state_path = root / "study-state.json"
    state = json.loads(state_path.read_text())
    kind = "rating" if tamper == "format" else "generation"
    task = next(task for task in state["tasks"] if task["kind"] == kind)
    capture = task["attempts"][0]["requests"][0]
    ref = capture["response" if tamper == "output" else "request"]
    artifact = root / ref["path"]
    changed = json.loads(artifact.read_text())
    if tamper == "protocol":
        changed["api_protocol"] = "chat_completions"
    elif tamper == "timeout":
        changed["timeout_seconds"] = 60
    elif tamper == "token_cap":
        changed["payload"]["max_output_tokens"] += 1
    elif tamper == "format":
        changed["payload"].pop("text")
    else:
        changed["output"][1]["content"][0]["text"] = "Forged answer."
    artifact.write_text(json.dumps(changed))
    ref["sha256"] = sha256(artifact.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValidationError):
        validate_study_state(root / "study.json", root)


@pytest.mark.parametrize("group", ["targets", "judges"])
@pytest.mark.parametrize("failure", ["incomplete", "empty", "unsupported_format"])
def test_failure_keeps_native_evidence_without_placeholder_or_parameter_fallback(
    tmp_path, scenario_factory, group, failure
):
    path, _ = write_inputs(tmp_path, scenario_factory)
    manifest = json.loads(path.read_text())
    manifest[group][0]["api_protocol"] = "responses"
    path.write_text(json.dumps(manifest))
    packets = []
    requests = []

    def transport(url, payload, headers, timeout):
        if not url.endswith("/responses"):
            return fake_transport(url, payload, headers, timeout)
        requests.append(deepcopy(payload))
        if failure == "unsupported_format":
            raise RuntimeError("endpoint rejected an unsupported parameter")
        packet = response_packet()
        if failure == "incomplete":
            packet.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        else:
            packet["output"] = [{"type": "reasoning", "summary": []}]
        packets.append(deepcopy(packet))
        return packet

    root = tmp_path / "run"
    result = run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)
    assert result["execution_status"] == "partial"
    checked = validate_study_state(root / "study.json", root)
    assert checked["rows"] == []
    kind = "generation" if group == "targets" else "rating"
    failed_tasks = [task for task in checked["tasks"] if task["kind"] == kind]
    assert all(task["status"] == "error" and not task["artifacts"] for task in failed_tasks)
    assert len(requests) == len(failed_tasks) * manifest["retry_attempts"]
    if group == "judges":
        assert all(request["text"] == {"format": {"type": "json_object"}} for request in requests)
    observed = []
    for task in failed_tasks:
        assert len(task["attempts"]) == manifest["retry_attempts"]
        for attempt in task["attempts"]:
            assert len(attempt["requests"]) == 1
            capture = attempt["requests"][0]
            if capture["response"]:
                observed.append(json.loads((root / capture["response"]["path"]).read_text()))
    assert observed == packets


def test_legacy_chat_payload_and_capture_bytes_are_preserved(tmp_path, scenario_factory):
    path, _ = write_inputs(tmp_path, scenario_factory)
    root = tmp_path / "run"
    calls = []

    def transport(url, payload, headers, timeout):
        assert timeout == 60.0
        calls.append({"url": url, "payload": deepcopy(payload)})
        return fake_transport(url, payload, headers, timeout)

    run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)
    checked = validate_study_state(root / "study.json", root)
    captures = [
        capture
        for task in checked["tasks"]
        for attempt in task["attempts"]
        for capture in attempt["requests"]
    ]
    for capture, expected in zip(captures, calls, strict=True):
        actual = (root / capture["request"]["path"]).read_text()
        assert actual == json.dumps(expected, ensure_ascii=False, indent=2) + "\n"
        keys = list(expected["payload"])
        if expected["payload"]["model"].startswith("target"):
            assert keys == ["model", "messages", "temperature", "max_tokens"]
        else:
            assert keys == ["model", "messages", "max_tokens", "response_format", "temperature"]


def test_optional_fields_match_manifest_schema():
    schema_path = Path(__file__).parents[1] / "schemas/automated-study-v0.8.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text()))
    manifest = study_manifest()
    validator.validate(manifest)
    manifest["targets"][0].update(api_protocol="responses", timeout_seconds=120)
    manifest["judges"][0].update(api_protocol="chat_completions", use_response_format=False)
    validate_study(manifest)
    validator.validate(manifest)
    manifest["targets"][0]["use_response_format"] = False
    assert not validator.is_valid(manifest)
