# KV Block Trace Animation

This tool visualizes v1 scheduler KV block usage as a grid animation.

## 1) Capture trace during execution

Tracing is enabled by default and writes to:

- `/tmp/vllm_kv_block_trace.jsonl`

Optional overrides:

- `VLLM_KV_BLOCK_TRACE_PATH=/custom/path/trace.jsonl`
- `VLLM_KV_BLOCK_TRACE_INTERVAL=1` (record every N steps)
- `VLLM_KV_BLOCK_TRACE_ENABLE=0` (disable tracing)

The scheduler writes one JSONL record per scheduling step. The file includes:

- free block count
- KV usage ratio
- running/waiting request IDs
- per-request block IDs
- global used block IDs for the step

## 2) Render animation after run

From repository root:

```bash
.venv/bin/python tools/profiler/kv_block_trace/animate_kv_block_trace.py \
  /tmp/vllm_kv_block_trace.jsonl \
  --output /tmp/kv_block_trace.gif \
  --fps 8 \
  --columns 64
```

Use `.mp4` output if you prefer:

```bash
.venv/bin/python tools/profiler/kv_block_trace/animate_kv_block_trace.py \
  /tmp/vllm_kv_block_trace.jsonl \
  --output /tmp/kv_block_trace.mp4
```

## 3) Render interactive HTML timeline (step scrubber + hover owners)

```bash
.venv/bin/python tools/profiler/kv_block_trace/render_kv_block_trace_html.py \
  /tmp/vllm_kv_block_trace.jsonl \
  --output /tmp/vllm_kv_block_trace.html \
  --columns 64 \
  --cell-size 10
```

Open the generated HTML in a browser. Features:

- step slider and play/pause
- per-step alloc/free deltas
- hover any block to see block ID and owner request IDs

## 4) Compute summary metrics

```bash
.venv/bin/python tools/profiler/kv_block_trace/summarize_kv_block_trace.py \
  /tmp/vllm_kv_block_trace.jsonl
```

Add `--json` for machine-readable output.

## 5) Recruiter showcase page

See [docs/community/kv-block-trace-showcase.md](docs/community/kv-block-trace-showcase.md)
for a polished demo flow, architecture diagram, and concise presentation script.

## Legend

- `free`: gray
- `used`: blue
- `allocated in step`: green
- `freed in step`: red
