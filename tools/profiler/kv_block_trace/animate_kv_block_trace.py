#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project

"""Render scheduler KV block trace JSONL as a block-grid animation."""

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from matplotlib.colors import ListedColormap


def _load_trace(path: Path) -> tuple[dict, list[dict]]:
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


def _make_grid(
    used_ids: set[int],
    prev_used_ids: set[int],
    num_total_blocks: int,
    rows: int,
    cols: int,
) -> np.ndarray:
    grid = np.zeros((rows, cols), dtype=np.int8)
    allocated_now = used_ids - prev_used_ids
    freed_now = prev_used_ids - used_ids

    for block_id in used_ids:
        if block_id >= num_total_blocks:
            continue
        row = block_id // cols
        col = block_id % cols
        if row < rows:
            grid[row, col] = 1

    for block_id in allocated_now:
        if block_id >= num_total_blocks:
            continue
        row = block_id // cols
        col = block_id % cols
        if row < rows:
            grid[row, col] = 2

    for block_id in freed_now:
        if block_id >= num_total_blocks:
            continue
        row = block_id // cols
        col = block_id % cols
        if row < rows:
            grid[row, col] = 3

    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_jsonl", type=Path, help="KV block trace JSONL path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("kv_block_trace.gif"),
        help="Animation output path (.gif or .mp4)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=8,
        help="Animation frames per second",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=64,
        help="Grid column count",
    )
    args = parser.parse_args()

    header, steps = _load_trace(args.trace_jsonl)
    num_total_blocks = int(header["num_total_blocks"])
    cols = max(1, args.columns)
    rows = max(1, math.ceil(num_total_blocks / cols))

    cmap = ListedColormap(
        [
            "#f5f5f5",  # free
            "#1f77b4",  # used
            "#2ca02c",  # allocated this step
            "#d62728",  # freed this step
        ]
    )

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    ax.set_title("KV Block Usage Timeline")
    ax.set_xlabel("Block Column")
    ax.set_ylabel("Block Row")

    initial_grid = np.zeros((rows, cols), dtype=np.int8)
    image = ax.imshow(initial_grid, cmap=cmap, vmin=0, vmax=3, interpolation="none")

    legend_text = (
        "0: free  |  1: used  |  2: allocated-in-step  |  3: freed-in-step"
    )
    footer = ax.text(
        0.0,
        -0.08,
        legend_text,
        transform=ax.transAxes,
        fontsize=9,
        ha="left",
        va="top",
    )

    step_text = ax.text(
        0.0,
        1.02,
        "",
        transform=ax.transAxes,
        fontsize=10,
        ha="left",
        va="bottom",
    )

    prev_used_ids: set[int] = set()

    def _update(frame_idx: int):
        nonlocal prev_used_ids
        step = steps[frame_idx]
        used_ids = set(step.get("used_block_ids", []))
        grid = _make_grid(used_ids, prev_used_ids, num_total_blocks, rows, cols)
        image.set_data(grid)

        scheduled_count = len(step.get("scheduled_req_ids", []))
        running_count = len(step.get("running_req_ids", []))
        waiting_count = len(step.get("waiting_req_ids", []))
        free_blocks = int(step.get("num_free_blocks", 0))
        usage = float(step.get("kv_cache_usage", 0.0))

        step_text.set_text(
            "step={}  scheduled={}  running={}  waiting={}  free={}  usage={:.2%}".format(
                step.get("step", frame_idx + 1),
                scheduled_count,
                running_count,
                waiting_count,
                free_blocks,
                usage,
            )
        )

        prev_used_ids = used_ids
        return image, step_text, footer

    anim = animation.FuncAnimation(
        fig,
        _update,
        frames=len(steps),
        interval=max(1, int(1000 / max(1, args.fps))),
        blit=False,
        repeat=False,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    suffix = args.output.suffix.lower()
    if suffix == ".gif":
        writer = animation.PillowWriter(fps=args.fps)
        anim.save(args.output, writer=writer)
    elif suffix == ".mp4":
        writer = animation.FFMpegWriter(fps=args.fps)
        anim.save(args.output, writer=writer)
    else:
        raise ValueError("--output must end with .gif or .mp4")

    print(f"Saved animation to: {args.output}")


if __name__ == "__main__":
    main()
