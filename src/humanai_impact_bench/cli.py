"""Command-line interface for HumanAI-Impact-Bench."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from humanai_impact_bench.deployment import (
    draft_evaluate,
    evaluate_gate,
    load_scenario_source,
    run_scenarios,
)
from humanai_impact_bench.scoring import score_annotations
from humanai_impact_bench.validation import (
    ValidationError,
    load_annotations,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="humanai-impact-bench",
        description="Validate, score, and gate HumanAI-Impact-Bench artifacts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate scenario JSONL")
    validate_parser.add_argument("path", type=Path)

    score_parser = subparsers.add_parser("score", help="score annotation JSONL")
    score_parser.add_argument("path", type=Path)
    score_parser.add_argument("--pretty", action="store_true", help="indent JSON output")

    run_parser = subparsers.add_parser(
        "run", help="run scenarios against an OpenAI-compatible target"
    )
    run_parser.add_argument("--scenarios", type=Path, required=True)
    run_parser.add_argument("--target-base-url", required=True)
    run_parser.add_argument("--target-model", required=True)
    run_parser.add_argument(
        "--candidate-digest",
        required=True,
        help="immutable candidate identifier (sha256:<digest> or git:<commit>)",
    )
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument(
        "--system-prompt-file",
        type=Path,
        help="optional deployed system prompt; its SHA-256 is recorded",
    )
    run_parser.add_argument(
        "--target-api-key-env",
        help="environment variable containing the target API key",
    )
    run_parser.add_argument(
        "--temperature",
        type=float,
        default=0,
        help="target sampling temperature (default: 0)",
    )
    run_parser.add_argument(
        "--omit-temperature",
        action="store_true",
        help="omit temperature and use the target provider's default",
    )
    run_parser.add_argument(
        "--max-tokens",
        type=int,
        help="optional maximum number of generated tokens per response",
    )
    run_parser.add_argument(
        "--top-p",
        type=float,
        help="optional target nucleus-sampling probability",
    )
    run_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="independent scenarios to run concurrently (default: 1)",
    )

    draft_parser = subparsers.add_parser(
        "draft-evaluate",
        help="create PREVIEW automated judge annotations and report",
    )
    draft_parser.add_argument("--scenarios", type=Path, required=True)
    draft_parser.add_argument("--transcripts", type=Path, required=True)
    draft_parser.add_argument("--judge-base-url", required=True)
    draft_parser.add_argument("--judge-model", required=True)
    draft_parser.add_argument("--output", type=Path, required=True)
    draft_parser.add_argument("--report", type=Path, required=True)
    draft_parser.add_argument(
        "--judge-api-key-env",
        help="environment variable containing the judge API key",
    )
    draft_parser.add_argument(
        "--omit-judge-temperature",
        action="store_true",
        help="omit judge temperature and use the provider default",
    )
    draft_parser.add_argument(
        "--omit-response-format",
        action="store_true",
        help="request JSON via the judge prompt without response_format",
    )
    draft_parser.add_argument(
        "--judge-workers",
        type=int,
        default=1,
        help="independent transcripts to judge concurrently (default: 1)",
    )
    draft_parser.add_argument(
        "--judge-retries",
        type=int,
        default=1,
        help="attempts per transcript for invalid or failed judge responses (default: 1)",
    )

    gate_parser = subparsers.add_parser("gate", help="check a report against a deployment policy")
    gate_parser.add_argument("--report", type=Path, required=True)
    gate_parser.add_argument("--policy", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            scenarios, _dataset_digest = load_scenario_source(args.path)
            languages = sorted({scenario["language"] for scenario in scenarios})
            print(
                json.dumps(
                    {
                        "valid": True,
                        "scenario_count": len(scenarios),
                        "languages": languages,
                    }
                )
            )
            return 0
        if args.command == "score":
            annotations = load_annotations(args.path)
            results = [result.to_dict() for result in score_annotations(annotations)]
            print(json.dumps(results, ensure_ascii=False, indent=2 if args.pretty else None))
            return 0
        if args.command == "run":
            result = run_scenarios(
                scenarios_path=args.scenarios,
                target_base_url=args.target_base_url,
                target_model=args.target_model,
                candidate_digest=args.candidate_digest,
                output_path=args.output,
                system_prompt_path=args.system_prompt_file,
                target_api_key_env=args.target_api_key_env,
                temperature=None if args.omit_temperature else args.temperature,
                max_tokens=args.max_tokens,
                top_p=args.top_p,
                workers=args.workers,
            )
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == "draft-evaluate":
            result = draft_evaluate(
                scenarios_path=args.scenarios,
                transcripts_path=args.transcripts,
                judge_base_url=args.judge_base_url,
                judge_model=args.judge_model,
                output_path=args.output,
                report_path=args.report,
                judge_api_key_env=args.judge_api_key_env,
                judge_temperature=None if args.omit_judge_temperature else 0,
                use_response_format=not args.omit_response_format,
                workers=args.judge_workers,
                judge_retries=args.judge_retries,
            )
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == "gate":
            result = evaluate_gate(report_path=args.report, policy_path=args.policy)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["gate_decision"] == "PASS" else 1
    except (ValidationError, RuntimeError) as exc:
        if args.command == "gate":
            print(
                json.dumps(
                    {
                        "tool": "HumanAI-Impact-Bench",
                        "gate_decision": "ERROR",
                        "deployment_action": "HOLD",
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            return 2
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
