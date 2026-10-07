#!/usr/bin/env python3
"""Generate a standalone HTML latency chart from a traffic log.

Expected log format (examples):
    2026-10-07 16:30:03 | FAILED | CURL_ERROR_56
    2026-10-07 16:30:11 | OK | 343 ms | HTTP 200

Only `OK` rows with `N ms` are plotted.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

TS_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \|")
OK_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| OK \| (\d+) ms(?: \|.*)?$"
)
TS_FMT = "%Y-%m-%d %H:%M:%S"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML chart (timestamp vs latency ms) from a traffic log.",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="Optional window size in minutes from the first timestamp in the log.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input traffic log file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output HTML file.",
    )

    args = parser.parse_args()

    if args.minutes is not None and args.minutes <= 0:
        parser.error("--minutes must be a positive integer")

    return args


def load_points(log_path: Path, minutes: int | None) -> tuple[list[dict[str, int]], datetime, datetime, int]:
    first_ts: datetime | None = None
    ok_rows: list[tuple[datetime, int]] = []

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()

            if first_ts is None:
                m_prefix = TS_PREFIX_RE.match(line)
                if m_prefix:
                    first_ts = datetime.strptime(m_prefix.group(1), TS_FMT)

            m_ok = OK_RE.match(line)
            if m_ok:
                ts = datetime.strptime(m_ok.group(1), TS_FMT)
                ms = int(m_ok.group(2))
                ok_rows.append((ts, ms))

    if first_ts is None:
        raise ValueError("No timestamped rows found in input log")

    if minutes is None:
        filtered = ok_rows
    else:
        end_ts = first_ts + timedelta(minutes=minutes)
        filtered = [(ts, ms) for ts, ms in ok_rows if first_ts <= ts <= end_ts]

    if not filtered:
        raise ValueError("No OK latency points found for the selected window")

    points = [{"t": int(ts.timestamp() * 1000), "ms": ms} for ts, ms in filtered]
    min_ts = min(ts for ts, _ in filtered)
    max_ts = max(ts for ts, _ in filtered)

    return points, min_ts, max_ts, len(filtered)


def build_html(points: Iterable[dict[str, int]], title_suffix: str, source_name: str) -> str:
    points_json = json.dumps(list(points), separators=(",", ":"))

    # Plain replacement placeholders avoid escaping braces for JS/CSS blocks.
    template = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Upload Latency Chart__TITLE_SUFFIX__</title>
  <style>
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif;
      background: #0b0f14;
      color: #e6edf3;
    }
    .wrap {
      max-width: 1400px;
      margin: 20px auto;
      padding: 0 16px 20px;
    }
    h1 { margin: 0 0 8px; font-size: 22px; }
    .meta { margin: 0 0 14px; color: #9fb0c0; font-size: 14px; }
    .card {
      background: #111827;
      border: 1px solid #253143;
      border-radius: 10px;
      padding: 12px;
      overflow-x: auto;
    }
    canvas { display: block; background: #0f1722; border-radius: 8px; }
    .hint { margin-top: 10px; color: #9fb0c0; font-size: 12px; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>Upload Latency Over Time__TITLE_SUFFIX__</h1>
    <p class=\"meta\" id=\"meta\"></p>
    <div class=\"card\">
      <canvas id=\"chart\" width=\"1300\" height=\"620\" aria-label=\"Upload latency chart\"></canvas>
    </div>
    <div class=\"hint\">Source: __SOURCE_NAME__ (OK entries with latency in ms)</div>
  </div>

  <script>
    const data = __POINTS_JSON__;

    const canvas = document.getElementById('chart');
    const ctx = canvas.getContext('2d');

    const W = canvas.width;
    const H = canvas.height;
    const margin = { top: 30, right: 24, bottom: 70, left: 70 };
    const plotW = W - margin.left - margin.right;
    const plotH = H - margin.top - margin.bottom;

    const minT = Math.min(...data.map(p => p.t));
    const maxT = Math.max(...data.map(p => p.t));
    const minMsRaw = Math.min(...data.map(p => p.ms));
    const maxMsRaw = Math.max(...data.map(p => p.ms));

    const pad = Math.max(5, Math.round((maxMsRaw - minMsRaw) * 0.08));
    const minMs = Math.max(0, minMsRaw - pad);
    const maxMs = maxMsRaw + pad;

    const x = t => margin.left + ((t - minT) / Math.max(1, (maxT - minT))) * plotW;
    const y = ms => margin.top + (1 - ((ms - minMs) / Math.max(1, (maxMs - minMs)))) * plotH;

    function clear() {
      ctx.fillStyle = '#0f1722';
      ctx.fillRect(0, 0, W, H);
    }

    function drawAxes() {
      ctx.strokeStyle = '#6b7f95';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(margin.left, margin.top);
      ctx.lineTo(margin.left, H - margin.bottom);
      ctx.lineTo(W - margin.right, H - margin.bottom);
      ctx.stroke();

      ctx.fillStyle = '#c9d6e2';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Timestamp', margin.left + plotW / 2, H - 22);

      ctx.save();
      ctx.translate(20, margin.top + plotH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillText('Latency (ms)', 0, 0);
      ctx.restore();
    }

    function fmtTime(ms) {
      const d = new Date(ms);
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }

    function drawYTicks(count = 7) {
      ctx.font = '11px sans-serif';
      ctx.fillStyle = '#9fb0c0';
      ctx.strokeStyle = '#1f2a38';
      ctx.lineWidth = 1;

      for (let i = 0; i < count; i++) {
        const v = minMs + (i * (maxMs - minMs) / (count - 1));
        const py = y(v);

        ctx.beginPath();
        ctx.moveTo(margin.left, py);
        ctx.lineTo(W - margin.right, py);
        ctx.stroke();

        ctx.textAlign = 'right';
        ctx.fillText(Math.round(v).toString(), margin.left - 8, py + 4);
      }
    }

    function drawXTicks(count = 8) {
      ctx.font = '11px sans-serif';
      ctx.fillStyle = '#9fb0c0';
      ctx.strokeStyle = '#1f2a38';

      for (let i = 0; i < count; i++) {
        const t = minT + (i * (maxT - minT) / Math.max(1, (count - 1)));
        const px = x(t);

        ctx.beginPath();
        ctx.moveTo(px, margin.top);
        ctx.lineTo(px, H - margin.bottom);
        ctx.stroke();

        ctx.save();
        ctx.translate(px, H - margin.bottom + 16);
        ctx.rotate(-Math.PI / 5);
        ctx.textAlign = 'left';
        ctx.fillText(fmtTime(t), 0, 0);
        ctx.restore();
      }
    }

    function drawSeries() {
      ctx.strokeStyle = '#58a6ff';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      data.forEach((p, i) => {
        const px = x(p.t), py = y(p.ms);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();

      ctx.fillStyle = '#7ee787';
      for (const p of data) {
        const px = x(p.t), py = y(p.ms);
        ctx.beginPath();
        ctx.arc(px, py, 1.9, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function setMeta() {
      const minV = Math.min(...data.map(d => d.ms));
      const maxV = Math.max(...data.map(d => d.ms));
      const avg = data.reduce((a, b) => a + b.ms, 0) / data.length;
      const start = fmtTime(minT);
      const end = fmtTime(maxT);
      document.getElementById('meta').textContent =
        `${data.length} points | min ${minV} ms | avg ${avg.toFixed(1)} ms | max ${maxV} ms | range: ${start} → ${end}`;
    }

    clear();
    drawYTicks();
    drawXTicks();
    drawAxes();
    drawSeries();
    setMeta();
  </script>
</body>
</html>
"""

    return (
        template.replace("__POINTS_JSON__", points_json)
        .replace("__TITLE_SUFFIX__", title_suffix)
        .replace("__SOURCE_NAME__", source_name)
    )


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input log file not found: {input_path}")

    points, min_ts, max_ts, count = load_points(input_path, args.minutes)

    title_suffix = f" (First {args.minutes} Minutes)" if args.minutes is not None else ""
    html = build_html(points, title_suffix, input_path.name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(
        "Wrote "
        f"{output_path} with {count} points; "
        f"range {min_ts.strftime(TS_FMT)} to {max_ts.strftime(TS_FMT)}"
    )


if __name__ == "__main__":
    main()
