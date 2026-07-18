#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project

"""Render KV block trace JSONL into a self-contained interactive HTML player."""

import argparse
import base64
import json
from pathlib import Path


def load_trace(path: Path) -> tuple[dict, list[dict]]:
    header = None
    steps: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            rtype = record.get("type")
            if rtype == "header":
                header = record
            elif rtype == "step":
                steps.append(record)

    if header is None:
        raise ValueError(f"Trace file {path} has no header record")
    if not steps:
        raise ValueError(f"Trace file {path} has no step records")
    return header, steps


def build_html(trace_payload_b64: str, columns: int, cell_size: int) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>KV Block Trace Player</title>
  <style>
    :root {{
      --bg: #f7f9fb;
      --surface: #ffffff;
      --ink: #1a1f36;
      --muted: #5f6b8a;
      --stroke: #d9dfeb;
      --free: #eef2f7;
      --used: #2b6cb0;
      --alloc: #2f9e44;
      --freed: #e03131;
      --null: #adb5bd;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      color: var(--ink);
      background: radial-gradient(circle at 15% 0%, #e8f1ff 0%, var(--bg) 40%);
    }}

    .layout {{
      display: grid;
      grid-template-columns: 1fr 320px;
      gap: 16px;
      padding: 16px;
      min-height: 100vh;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid var(--stroke);
      border-radius: 14px;
      box-shadow: 0 6px 24px rgba(12, 27, 66, 0.08);
      overflow: hidden;
    }}

    .left {{
      display: grid;
      grid-template-rows: auto auto 1fr;
      gap: 12px;
    }}

    .head {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--stroke);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }}

    .title {{ font-size: 14px; font-weight: 700; letter-spacing: 0.2px; }}
    .meta {{ color: var(--muted); font-size: 12px; }}

    .controls {{
      padding: 10px 14px 12px;
      display: grid;
      gap: 8px;
    }}

    .row {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 10px;
      align-items: center;
      font-size: 12px;
    }}

    button, select {{
      border: 1px solid var(--stroke);
      background: #fff;
      border-radius: 8px;
      padding: 6px 10px;
      font: inherit;
      cursor: pointer;
    }}

    input[type=range] {{ width: 100%; }}

    .canvas-wrap {{
      position: relative;
      padding: 12px;
      overflow: auto;
      border-top: 1px solid var(--stroke);
    }}

    canvas {{
      border: 1px solid var(--stroke);
      border-radius: 10px;
      background: #fff;
      image-rendering: pixelated;
    }}

    .legend {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 8px;
      font-size: 11px;
      color: var(--muted);
      padding: 10px 14px 14px;
      border-top: 1px solid var(--stroke);
    }}

    .chip {{ display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }}
    .sw {{ width: 10px; height: 10px; border-radius: 2px; border: 1px solid #cfd6e6; }}

    .side {{ display: grid; grid-template-rows: auto auto 1fr; }}

    .stats {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--stroke);
      display: grid;
      gap: 6px;
      font-size: 12px;
    }}

    .requests {{
      padding: 12px 14px;
      overflow: auto;
      font-size: 12px;
    }}

    .requests code {{ font-family: inherit; font-size: 11px; }}

    .hoverbox {{
      position: fixed;
      pointer-events: none;
      transform: translate(10px, 10px);
      background: rgba(17, 24, 39, 0.94);
      color: #f8fafc;
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 11px;
      line-height: 1.35;
      display: none;
      max-width: 360px;
      z-index: 2000;
    }}

    @media (max-width: 1100px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .side {{ min-height: 280px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <section class="panel left">
      <div class="head">
        <div class="title">KV Block Trace Player</div>
        <div class="meta" id="meta"></div>
      </div>

      <div class="controls">
        <div class="row">
          <button id="play">Play</button>
          <input id="stepRange" type="range" min="0" value="0" />
          <div id="stepLabel">step 0 / 0</div>
        </div>
        <div class="row">
          <label for="speed">Speed</label>
          <select id="speed">
            <option value="1">1x</option>
            <option value="2">2x</option>
            <option value="4">4x</option>
            <option value="8">8x</option>
          </select>
          <div id="summary"></div>
        </div>
      </div>

      <div class="canvas-wrap">
        <canvas id="grid"></canvas>
      </div>

      <div class="legend">
        <span class="chip"><span class="sw" style="background: var(--free)"></span>free</span>
        <span class="chip"><span class="sw" style="background: var(--used)"></span>used</span>
        <span class="chip"><span class="sw" style="background: var(--alloc)"></span>allocated in step</span>
        <span class="chip"><span class="sw" style="background: var(--freed)"></span>freed in step</span>
        <span class="chip"><span class="sw" style="background: var(--null)"></span>null block</span>
      </div>
    </section>

    <aside class="panel side">
      <div class="head">
        <div class="title">Step Details</div>
      </div>
      <div class="stats" id="stats"></div>
      <div class="requests" id="requests"></div>
    </aside>
  </div>

  <div class="hoverbox" id="hoverbox"></div>

  <script>
    const tracePayload = JSON.parse(atob("{trace_payload_b64}"));
    const header = tracePayload.header;
    const steps = tracePayload.steps;
    const cols = {columns};
    const cellSize = {cell_size};
    const nullBlockId = 0;

    const colors = {{
      free: getComputedStyle(document.documentElement).getPropertyValue("--free").trim(),
      used: getComputedStyle(document.documentElement).getPropertyValue("--used").trim(),
      alloc: getComputedStyle(document.documentElement).getPropertyValue("--alloc").trim(),
      freed: getComputedStyle(document.documentElement).getPropertyValue("--freed").trim(),
      nullBlock: getComputedStyle(document.documentElement).getPropertyValue("--null").trim(),
      stroke: "#cfd6e6",
    }};

    const canvas = document.getElementById("grid");
    const ctx = canvas.getContext("2d");
    const slider = document.getElementById("stepRange");
    const playBtn = document.getElementById("play");
    const speedSel = document.getElementById("speed");
    const stepLabel = document.getElementById("stepLabel");
    const summary = document.getElementById("summary");
    const stats = document.getElementById("stats");
    const requests = document.getElementById("requests");
    const hoverbox = document.getElementById("hoverbox");
    const meta = document.getElementById("meta");

    const totalBlocks = header.num_total_blocks;
    const rows = Math.max(1, Math.ceil(totalBlocks / cols));
    canvas.width = cols * cellSize;
    canvas.height = rows * cellSize;

    meta.textContent = `blocks=${{totalBlocks}}  groups=${{header.num_kv_groups}}  steps=${{steps.length}}`;
    slider.max = String(steps.length - 1);

    let currentIndex = 0;
    let isPlaying = false;
    let timerId = null;
    let ownerMap = new Map();

    function blockCell(blockId) {{
      const row = Math.floor(blockId / cols);
      const col = blockId % cols;
      return {{ row, col }};
    }}

    function stepSet(step, key) {{
      return new Set(step[key] || []);
    }}

    function buildOwnerMap(step) {{
      const map = new Map();
      const reqBlocks = step.req_blocks || {{}};
      for (const [reqId, groups] of Object.entries(reqBlocks)) {{
        for (const group of groups) {{
          for (const blockId of group) {{
            if (!map.has(blockId)) map.set(blockId, []);
            map.get(blockId).push(reqId);
          }}
        }}
      }}
      return map;
    }}

    function drawGrid(prevStep, currStep) {{
      const prevUsed = prevStep ? stepSet(prevStep, "used_block_ids") : new Set();
      const used = stepSet(currStep, "used_block_ids");

      const alloc = new Set([...used].filter((x) => !prevUsed.has(x)));
      const freed = new Set([...prevUsed].filter((x) => !used.has(x)));

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let blockId = 0; blockId < totalBlocks; blockId++) {{
        const {{row, col}} = blockCell(blockId);
        const x = col * cellSize;
        const y = row * cellSize;

        let color = colors.free;
        if (blockId === nullBlockId) color = colors.nullBlock;
        if (used.has(blockId)) color = colors.used;
        if (alloc.has(blockId)) color = colors.alloc;
        if (freed.has(blockId)) color = colors.freed;

        ctx.fillStyle = color;
        ctx.fillRect(x, y, cellSize, cellSize);
      }}

      ctx.strokeStyle = colors.stroke;
      ctx.lineWidth = 0.2;
      for (let r = 0; r <= rows; r++) {{
        const y = r * cellSize;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }}
      for (let c = 0; c <= cols; c++) {{
        const x = c * cellSize;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }}

      return {{ usedCount: used.size, allocCount: alloc.size, freedCount: freed.size }};
    }}

    function render(index) {{
      currentIndex = Math.max(0, Math.min(steps.length - 1, index));
      slider.value = String(currentIndex);

      const curr = steps[currentIndex];
      const prev = currentIndex > 0 ? steps[currentIndex - 1] : null;
      ownerMap = buildOwnerMap(curr);

      const diff = drawGrid(prev, curr);
      const usagePct = ((curr.kv_cache_usage || 0) * 100).toFixed(2);

      stepLabel.textContent = `step ${{curr.step}} / ${{steps[steps.length - 1].step}}`;
      summary.textContent = `used=${{diff.usedCount}} alloc=${{diff.allocCount}} freed=${{diff.freedCount}}`;

      stats.innerHTML = [
        `step: <b>${{curr.step}}</b>`,
        `free blocks: <b>${{curr.num_free_blocks}}</b>`,
        `usage: <b>${{usagePct}}%</b>`,
        `running reqs: <b>${{(curr.running_req_ids || []).length}}</b>`,
        `waiting reqs: <b>${{(curr.waiting_req_ids || []).length}}</b>`,
        `scheduled reqs: <b>${{(curr.scheduled_req_ids || []).length}}</b>`,
      ].join("<br />");

      const running = curr.running_req_ids || [];
      const waiting = curr.waiting_req_ids || [];
      const scheduled = curr.scheduled_req_ids || [];
      requests.innerHTML = `
        <div><b>scheduled</b>: <code>${{scheduled.join(", ") || "-"}}</code></div>
        <div style="margin-top:8px"><b>running</b>: <code>${{running.join(", ") || "-"}}</code></div>
        <div style="margin-top:8px"><b>waiting</b>: <code>${{waiting.join(", ") || "-"}}</code></div>
      `;
    }}

    function stopPlayback() {{
      if (timerId !== null) {{
        clearInterval(timerId);
        timerId = null;
      }}
      isPlaying = false;
      playBtn.textContent = "Play";
    }}

    function startPlayback() {{
      stopPlayback();
      isPlaying = true;
      playBtn.textContent = "Pause";
      const speed = Number(speedSel.value || "1");
      const intervalMs = Math.max(30, Math.floor(250 / speed));

      timerId = setInterval(() => {{
        if (currentIndex >= steps.length - 1) {{
          stopPlayback();
          return;
        }}
        render(currentIndex + 1);
      }}, intervalMs);
    }}

    playBtn.addEventListener("click", () => {{
      if (isPlaying) stopPlayback();
      else startPlayback();
    }});

    speedSel.addEventListener("change", () => {{
      if (isPlaying) startPlayback();
    }});

    slider.addEventListener("input", () => {{
      render(Number(slider.value));
    }});

    canvas.addEventListener("mousemove", (e) => {{
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const col = Math.floor(x / cellSize);
      const row = Math.floor(y / cellSize);
      const blockId = row * cols + col;

      if (col < 0 || row < 0 || blockId >= totalBlocks) {{
        hoverbox.style.display = "none";
        return;
      }}

      const owners = ownerMap.get(blockId) || [];
      hoverbox.style.display = "block";
      hoverbox.style.left = `${{e.clientX}}px`;
      hoverbox.style.top = `${{e.clientY}}px`;
      hoverbox.innerHTML = `
        block_id: <b>${{blockId}}</b><br/>
        row: <b>${{row}}</b> col: <b>${{col}}</b><br/>
        owners: <b>${{owners.length ? owners.join(", ") : "-"}}</b>
      `;
    }});

    canvas.addEventListener("mouseleave", () => {{
      hoverbox.style.display = "none";
    }});

    render(0);
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace_jsonl",
        nargs="?",
        type=Path,
        default=Path("/tmp/vllm_kv_block_trace.jsonl"),
        help="KV block trace JSONL path (default: /tmp/vllm_kv_block_trace.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/vllm_kv_block_trace.html"),
        help="Output HTML path",
    )
    parser.add_argument(
        "--columns",
        type=int,
        default=64,
        help="Grid column count",
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=10,
        help="Pixel size for each block cell",
    )
    args = parser.parse_args()

    header, steps = load_trace(args.trace_jsonl)
    payload = json.dumps({"header": header, "steps": steps}, separators=(",", ":"))
    payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    html = build_html(
        trace_payload_b64=payload_b64,
        columns=max(1, args.columns),
        cell_size=max(2, args.cell_size),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote HTML player: {args.output}")


if __name__ == "__main__":
    main()
