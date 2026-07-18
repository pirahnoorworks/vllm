# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project

import json
import os
import time
from collections.abc import Sequence
from typing import Any


class KVBlockTraceWriter:
    """Writes scheduler-step KV block snapshots as JSONL records.

    Records are append-only so they can be tailed while the scheduler is
    running and replayed later for animation.
    """

    def __init__(self, output_path: str, num_total_blocks: int, num_groups: int):
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        self._file = open(output_path, "w", encoding="utf-8")
        self._write_record(
            {
                "type": "header",
                "version": 1,
                "created_at": time.time(),
                "num_total_blocks": num_total_blocks,
                "num_kv_groups": num_groups,
            }
        )

    def close(self) -> None:
        if self._file.closed:
            return
        self._file.flush()
        self._file.close()

    def write_step(
        self,
        *,
        step: int,
        num_free_blocks: int,
        kv_cache_usage: float,
        running_req_ids: Sequence[str],
        waiting_req_ids: Sequence[str],
        skipped_waiting_req_ids: Sequence[str],
        scheduled_req_ids: Sequence[str],
        req_blocks: dict[str, list[list[int]]],
        used_block_ids: list[int],
    ) -> None:
        self._write_record(
            {
                "type": "step",
                "ts": time.time(),
                "step": step,
                "num_free_blocks": num_free_blocks,
                "kv_cache_usage": kv_cache_usage,
                "running_req_ids": list(running_req_ids),
                "waiting_req_ids": list(waiting_req_ids),
                "skipped_waiting_req_ids": list(skipped_waiting_req_ids),
                "scheduled_req_ids": list(scheduled_req_ids),
                "req_blocks": req_blocks,
                "used_block_ids": used_block_ids,
            }
        )

    def _write_record(self, record: dict[str, Any]) -> None:
        self._file.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._file.flush()
