"""Manual real-provider runner for NAC/ITU Candidate Graph experiments."""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from cpg_tree.candidates.graph_serialization import (
    write_candidate_graph,
    write_generation_quarantine,
)
from cpg_tree.candidates.hashing import sha256_hex
from cpg_tree.extraction import extract_document_map
from cpg_tree.extraction.serialization import load_document_map
from cpg_tree.llm.provider import OpenAICompatibleProvider
from cpg_tree.pipelines.semantic import (
    SemanticPipelineConfig,
    SemanticPipelineError,
    run_semantic_pipeline,
)


def main(argv: list[str] | None = None) -> int:
    """Run the semantic pipeline explicitly; never invoked by normal tests or CI."""
    parser = argparse.ArgumentParser(
        prog="python -m cpg_tree.llm.run",
        description="Run LLM-first candidate generation from a PDF or DocumentMap YAML.",
    )
    parser.add_argument("source", help="local PDF or serialized DocumentMap YAML")
    parser.add_argument("--protocol-version-id", required=True)
    parser.add_argument("--protocol-id", help="required when SOURCE is a raw PDF")
    parser.add_argument("--protocol-version", help="required when SOURCE is a raw PDF")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CPG_TREE_LLM_BASE_URL"),
        help="OpenAI-compatible API base URL (or CPG_TREE_LLM_BASE_URL)",
    )
    parser.add_argument("--api-key-env", default="CPG_TREE_LLM_API_KEY")
    parser.add_argument("--provider-name", default="openai-compatible")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--run-id")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if not args.base_url:
        parser.error("--base-url or CPG_TREE_LLM_BASE_URL is required")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        parser.error(f"environment variable {args.api_key_env!r} is required")

    source = Path(args.source)
    if source.suffix.lower() == ".pdf":
        document_map = extract_document_map(source)
        if not args.protocol_id or not args.protocol_version:
            parser.error("raw PDF input requires --protocol-id and --protocol-version")
        document_map = replace(
            document_map,
            document=replace(
                document_map.document,
                protocol_id=args.protocol_id,
                protocol_version=args.protocol_version,
            ),
        )
    else:
        document_map = load_document_map(source.read_text(encoding="utf-8"))
    generation_run_id = args.run_id or (
        f"gen-{document_map.document.sha256[:8]}-{sha256_hex(args.model)[:6]}-"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{time.time_ns():x}"
    )
    provider = OpenAICompatibleProvider(
        base_url=args.base_url,
        api_key=api_key,
        model=args.model,
        provider_name=args.provider_name,
    )
    output = (
        Path(args.out)
        if args.out
        else Path("data/runs") / generation_run_id / "candidate_graph.json"
    )
    try:
        result = run_semantic_pipeline(
            document_map,
            provider,
            SemanticPipelineConfig(
                generation_run_id=generation_run_id,
                protocol_version_id=args.protocol_version_id,
                temperature=args.temperature,
                reasoning_effort=args.reasoning_effort,
                max_retries=args.max_retries,
            ),
        )
    except SemanticPipelineError as exc:
        quarantine_path = output.with_name(f"{output.stem}.quarantine.json")
        write_generation_quarantine(exc.attempts, quarantine_path)
        print(f"quarantine      : {quarantine_path}")
        return 1
    write_candidate_graph(result.graph, output)
    print(f"candidate_graph : {result.graph.graph_id}")
    print(f"rules           : {len(result.graph.rules)}")
    print(f"relations       : {len(result.graph.relations)}")
    print(f"issues          : {len(result.graph.issues)}")
    print(f"findings        : {len(result.graph.findings)}")
    print(f"artifact        : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
