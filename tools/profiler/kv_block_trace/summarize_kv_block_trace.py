#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project

"""Summarize KV block trace JSONL with recruiter-friendly metrics."""

import argparse
import json
from pathlib import Path


def load_steps(path: Path) -> tuple[dict, list[dict]]:
    header = None
    steps: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("type") == "header":
                header = rec
            elif rec.get("type") == "step":
                steps.append(rec)

    if header is None:
        raise ValueError(f"Trace file {path} has no header record")
    if not steps:
        raise ValueError(f"Trace file {path} has no step records")
    return header, steps


def compute_summary(header: dict, steps: list[dict]) -> dict:
    free_blocks = [int(step.get("num_free_blocks", 0)) for step in steps]
    usage = [float(step.get("kv_cache_usage", 0.0)) for step in steps]

    alloc_counts: list[int] = []
    free_counts: list[int] = []
    prev_used: set[int] = set()

    for step in steps:
        used = set(step.get("used_block_ids", []))
        alloc_counts.append(len(used - prev_used))
        free_counts.append(len(prev_used - used))
        prev_used = used

    peak_usage = max(usage)
    avg_usage = sum(usage) / len(usage)
    min_free = min(free_blocks)
    avg_free = sum(free_blocks) / len(free_blocks)

    avg_alloc = sum(alloc_counts) / len(alloc_counts)
    avg_freed = sum(free_counts) / len(free_counts)
    avg_churn = sum(a + b for a, b in zip(alloc_counts, free_counts)) / len(steps)

    max_running = max(len(step.get("running_req_ids", [])) for step in steps)
    max_waiting = max(len(step.get("waiting_req_ids", [])) for step in steps)

    return {
        "trace_version": header.get("version", 1),
        "num_total_blocks": header.get("num_total_blocks"),
        "num_kv_groups": header.get("num_kv_groups"),
        "num_steps": len(steps),
        "peak_usage_ratio": peak_usage,
        "peak_usage_percent": 100.0 * peak_usage,
        "avg_usage_ratio": avg_usage,
        "avg_usage_percent": 100.0 * avg_usage,
        "min_free_blocks": min_free,
        "avg_free_blocks": avg_free,
        "avg_allocated_blocks_per_step": avg_alloc,
        "avg_freed_blocks_per_step": avg_freed,
        "avg_block_churn_per_step": avg_churn,
        "max_running_requests": max_running,
        "max_waiting_requests": max_waiting,
    }


def print_human(summary: dict) -> None:
    print("KV block trace summary")
    print("-" * 64)
    print(f"steps: {summary['num_steps']}")
    print(f"total blocks: {summary['num_total_blocks']}")
    print(f"kv groups: {summary['num_kv_groups']}")
    print(f"peak usage: {summary['peak_usage_percent']:.2f}%")
    print(f"avg usage: {summary['avg_usage_percent']:.2f}%")
    print(f"min free blocks: {summary['min_free_blocks']}")
    print(f"avg free blocks: {summary['avg_free_blocks']:.2f}")
    print(
        "avg alloc/free per step: "
        f"{summary['avg_allocated_blocks_per_step']:.2f} / "
        f"{summary['avg_freed_blocks_per_step']:.2f}"
    )
    print(f"avg churn per step: {summary['avg_block_churn_per_step']:.2f}")
    print(f"max running reqs: {summary['max_running_requests']}")
    print(f"max waiting reqs: {summary['max_waiting_requests']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace_jsonl",
        nargs="?",
        type=Path,
        default=Path("/tmp/vllm_kv_block_trace.jsonl"),
        help="KV block trace JSONL path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    args = parser.parse_args()

    header, steps = load_steps(args.trace_jsonl)
    summary = compute_summary(header, steps)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary)


if __name__ == "__main__":
    main()
