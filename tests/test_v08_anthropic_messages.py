from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from humanai_impact_bench import api_protocols as api
from humanai_impact_bench.automated_evidence import (
    verify_automated_evidence,
    write_evidence_bundle,
)
from humanai_impact_bench.experiments import run_study, validate_study, validate_study_state
from humanai_impact_bench.robustness import report_study
from humanai_impact_bench.validation import ValidationError
from tests.test_v08_api_protocols import response_packet
from tests.test_v08_experiments import fake_transport, study_manifest, write_inputs


def native_config():
    return {
        **study_manifest()["judges"][0],
        "api_protocol": "anthropic_messages",
        "use_response_format": False,
    }


def native_packet(text="A complete answer."):
    return {
        "id": "msg-provider-native",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "Private reasoning", "signature": "opaque"},
            {"type": "redacted_thinking", "data": "opaque"},
            {"type": "text", "text": text},
        ],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 40, "output_tokens": 12},
    }


@pytest.mark.parametrize("systems", [[], ["Pinned system."], ["First system.", "Second system."]])
def test_native_payload_preserves_system_boundaries_and_optional_temperature(systems):
    config = native_config()
    config["temperature"] = None
    messages = [{"role": "system", "content": text} for text in systems] + [
        {"role": "user", "content": "Earlier question."},
        {"role": "assistant", "content": "Earlier answer."},
        {"role": "user", "content": "Return JSON."},
    ]
    original = deepcopy(messages)
    payload = api.request_payload(config, messages, judge=True)
    assert api.endpoint(config) == "https://judge.example/v1/messages"
    assert payload["messages"] == messages[len(systems) :]
    assert payload["max_tokens"] == 64
    assert "temperature" not in payload
    assert set(payload) == {"model", "messages", "max_tokens"} | ({"system"} if systems else set())
    if len(systems) == 1:
        assert payload["system"] == systems[0]
    elif systems:
        assert payload["system"] == [{"type": "text", "text": text} for text in systems]
    assert api.canonical_messages(config, payload) == messages == original


def test_native_payload_rejects_nonleading_system_message():
    with pytest.raises(ValidationError, match="leading system"):
        api.request_payload(
            native_config(),
            [{"role": "user", "content": "Question"}, {"role": "system", "content": "Late"}],
        )


def test_native_version_header_preserves_authentication_without_capturing_it():
    config = native_config()
    original = {"Authorization": "Bearer mock-only", "Content-Type": "application/json"}
    headers = api.request_headers(config, original)
    assert headers == {**original, "anthropic-version": "2023-06-01"}
    assert "anthropic-version" not in original
    capture = api.request_record(config, api.endpoint(config), {}, headers=headers)
    assert capture["headers"] == {"anthropic-version": "2023-06-01"}
    assert "mock-only" not in json.dumps(capture)
    for invalid in ({}, {"anthropic-version": "wrong"}):
        with pytest.raises(ValidationError, match="version header"):
            api.request_record(config, api.endpoint(config), {}, headers=invalid)


def test_native_text_extraction_ignores_thinking_without_mutating_evidence():
    packet = native_packet("First ")
    packet["content"].append({"type": "text", "text": "second."})
    original = deepcopy(packet)
    assert api.assistant_content(packet, native_config()) == "First second."
    assert packet == original


@pytest.mark.parametrize(
    "change",
    [
        {"stop_reason": reason}
        for reason in (None, "max_tokens", "stop_sequence", "tool_use", "pause_turn", "refusal")
    ]
    + [
        {"stop_sequence": "unexpected"},
        {"type": "error"},
        {"role": "user"},
        {"status": "incomplete"},
        {"incomplete_details": {"reason": "max_tokens"}},
        {"content": []},
        {"content": "not an array"},
        {"content": [{"type": "thinking", "thinking": "Only private reasoning"}]},
        {"content": [{"type": "text", "text": " "}]},
        {"content": [{"type": "text", "text": 42}]},
        {"content": [{"type": "text", "text": "Visible"}, {"type": "tool_use"}]},
    ],
)
def test_native_incomplete_empty_and_tool_outputs_are_rejected(change):
    packet = native_packet()
    packet.update(change)
    with pytest.raises(RuntimeError):
        api.assistant_content(packet, native_config())


@pytest.mark.parametrize("setting", [None, True, False])
def test_native_judge_requires_explicit_format_omission_in_manifest_and_schema(setting):
    manifest = study_manifest()
    manifest["judges"][0]["api_protocol"] = "anthropic_messages"
    if setting is not None:
        manifest["judges"][0]["use_response_format"] = setting
    schema = Path(__file__).parents[1] / "schemas/automated-study-v0.8.schema.json"
    validator = Draft202012Validator(json.loads(schema.read_text()))
    if setting is False:
        validate_study(manifest)
        validator.validate(manifest)
    else:
        with pytest.raises(ValidationError, match="explicit use_response_format=false"):
            validate_study(manifest)
        with pytest.raises(ValidationError, match="explicit use_response_format=false"):
            api.request_payload(manifest["judges"][0], [], judge=True)
        assert not validator.is_valid(manifest)


def configure_study(tmp_path, scenario_factory, target_protocol, judge_protocol):
    path, _ = write_inputs(tmp_path, scenario_factory)
    manifest = json.loads(path.read_text())
    (tmp_path / "system.txt").write_text("You are a helpful assistant.")
    manifest["system_prompt_path"] = "system.txt"
    for group, protocol in (("targets", target_protocol), ("judges", judge_protocol)):
        manifest[group][0].update(api_protocol=protocol, timeout_seconds=120, temperature=None)
    if judge_protocol == "anthropic_messages":
        manifest["judges"][0]["use_response_format"] = False
    path.write_text(json.dumps(manifest))
    return path, manifest


def mixed_transport(url, payload, headers, timeout):
    native = url.endswith("/messages")
    responses = url.endswith("/responses")
    config = {
        "api_protocol": "anthropic_messages"
        if native
        else "responses"
        if responses
        else "chat_completions"
    }
    messages = api.canonical_messages(config, payload)
    assert timeout == 120
    if native:
        assert headers["anthropic-version"] == "2023-06-01"
        assert "response_format" not in payload and "text" not in payload
        assert "system" in payload
        assert all(message["role"] != "system" for message in payload["messages"])
    chat_payload = {
        "model": payload["model"],
        "messages": messages,
        "max_tokens": payload["max_output_tokens" if responses else "max_tokens"],
    }
    packet = fake_transport(url, chat_payload, headers, timeout)
    text = packet["choices"][0]["message"]["content"]
    return native_packet(text) if native else response_packet(text) if responses else packet


@pytest.mark.parametrize(
    "target_protocol,judge_protocol",
    [
        ("anthropic_messages", "anthropic_messages"),
        ("anthropic_messages", "responses"),
        ("responses", "anthropic_messages"),
        ("anthropic_messages", "chat_completions"),
        ("chat_completions", "anthropic_messages"),
    ],
)
def test_native_candidate_and_judge_complete_and_verify_bundle(
    tmp_path, scenario_factory, target_protocol, judge_protocol
):
    path, _ = configure_study(tmp_path, scenario_factory, target_protocol, judge_protocol)
    root = tmp_path / "run"
    calls = []

    def transport(url, payload, headers, timeout):
        packet = mixed_transport(url, payload, headers, timeout)
        calls.append((deepcopy(payload), deepcopy(packet)))
        return packet

    result = run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)
    assert result["execution_status"] == "complete"
    checked = validate_study_state(root / "study.json", root)
    assert len(checked["rows"]) == 2
    captures = [c for t in checked["tasks"] for a in t["attempts"] for c in a["requests"]]
    for capture, (payload, packet) in zip(captures, calls, strict=True):
        request = json.loads((root / capture["request"]["path"]).read_text())
        assert request["payload"] == payload
        assert json.loads((root / capture["response"]["path"]).read_text()) == packet
        if request["api_protocol"] == "anthropic_messages":
            assert request["headers"] == {"anthropic-version": "2023-06-01"}
    report_study(manifest_path=root / "study.json", run_root=root, output_path=root / "report.json")
    write_evidence_bundle(root, root / "report.json", root / "bundle.json")
    assert verify_automated_evidence(root / "bundle.json")["execution_status"] == "complete"


@pytest.mark.parametrize("kind", ["generation", "rating"])
@pytest.mark.parametrize(
    "tamper", ["headers", "missing_header", "system", "token_cap", "protocol", "cutoff", "format"]
)
def test_native_rehashed_tampering_is_rejected(tmp_path, scenario_factory, kind, tamper):
    path, _ = configure_study(
        tmp_path, scenario_factory, "anthropic_messages", "anthropic_messages"
    )
    root = tmp_path / "run"
    run_study(manifest_path=path, output_root=root, dry_run=False, transport=mixed_transport)
    state_path = root / "study-state.json"
    state = json.loads(state_path.read_text())
    task = next(task for task in state["tasks"] if task["kind"] == kind)
    capture = task["attempts"][0]["requests"][0]
    ref = capture["response" if tamper == "cutoff" else "request"]
    artifact = root / ref["path"]
    changed = json.loads(artifact.read_text())
    if tamper == "headers":
        changed["headers"]["anthropic-version"] = "wrong"
    elif tamper == "missing_header":
        changed.pop("headers")
    elif tamper == "system":
        changed["payload"]["system"] = "Forged system instructions."
    elif tamper == "token_cap":
        changed["payload"]["max_tokens"] += 1
    elif tamper == "protocol":
        changed["api_protocol"] = "chat_completions"
    elif tamper == "format":
        changed["payload"]["response_format"] = {"type": "json_object"}
    else:
        changed["stop_reason"] = "max_tokens"
    artifact.write_text(json.dumps(changed))
    ref["sha256"] = sha256(artifact.read_bytes()).hexdigest()
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValidationError):
        validate_study_state(root / "study.json", root)


@pytest.mark.parametrize("group", ["targets", "judges"])
@pytest.mark.parametrize("failure", ["cutoff", "empty", "tool_use", "invalid_json"])
def test_native_failed_attempts_preserve_packets_and_do_not_score(
    tmp_path, scenario_factory, group, failure
):
    if group == "targets" and failure == "invalid_json":
        pytest.skip("Candidate output is plain text, not judge JSON")
    path, manifest = configure_study(
        tmp_path, scenario_factory, "anthropic_messages", "anthropic_messages"
    )
    packets = []

    def transport(url, payload, headers, timeout):
        packet = mixed_transport(url, payload, headers, timeout)
        target = payload["model"].startswith("target")
        if target == (group == "targets"):
            if failure == "cutoff":
                packet["stop_reason"] = "max_tokens"
            elif failure == "empty":
                packet["content"] = packet["content"][:2]
            elif failure == "tool_use":
                packet["content"].append({"type": "tool_use", "name": "unsupported"})
            else:
                packet["content"] = [{"type": "text", "text": "Not valid JSON"}]
            packets.append(deepcopy(packet))
        return packet

    root = tmp_path / "run"
    result = run_study(manifest_path=path, output_root=root, dry_run=False, transport=transport)
    assert result["execution_status"] == "partial"
    checked = validate_study_state(root / "study.json", root)
    assert checked["rows"] == []
    kind = "generation" if group == "targets" else "rating"
    failed = [task for task in checked["tasks"] if task["kind"] == kind]
    observed = []
    for task in failed:
        assert task["status"] == "error" and not task["artifacts"]
        assert len(task["attempts"]) == manifest["retry_attempts"]
        for attempt in task["attempts"]:
            assert len(attempt["requests"]) == 1
            capture = attempt["requests"][0]
            observed.append(json.loads((root / capture["response"]["path"]).read_text()))
    assert observed == packets
