# Traffic Logger

A lightweight upload latency monitor that:

- continuously uploads a test file to an endpoint and logs results (`traffic-monitor.sh`)
- generates a standalone HTML latency chart from the log (`generate_latency_chart.py`)

## Files

- `traffic-monitor.sh` — sends repeated upload requests and appends latency/status lines to `upload-latency.log`
- `generate_latency_chart.py` — parses the log and creates a chart HTML file
- `upload-latency.log` — sample/output log file
- `upload-latency-chart*.html` — generated chart examples

## Requirements

- macOS/Linux shell with `bash`
- `curl`
- `python3`

## 1) Collect upload latency data

From the project directory:

```bash
chmod +x traffic-monitor.sh
./traffic-monitor.sh
```

Press `Ctrl+C` to stop.

### Default monitor settings

In `traffic-monitor.sh`:

- `SERVER_URL="http://dlptest.com/api/http-post/"`
- `TEST_FILE="/tmp/latency-test.bin"` (auto-created as 1MB if missing)
- `INTERVAL=0` (runs continuously with no delay)
- `CONNECT_TIMEOUT=10`
- `MAX_TIME=60`
- `LOG_FILE="./upload-latency.log"`

If needed, edit these variables at the top of the script.

## 2) Generate chart(s)

Generate a chart from the full log:

```bash
python3 generate_latency_chart.py \
  --input upload-latency.log \
  --output upload-latency-chart-all.html
```

Generate a chart for only the first N minutes from the first log timestamp:

```bash
python3 generate_latency_chart.py \
  --minutes 10 \
  --input upload-latency.log \
  --output upload-latency-chart-10m.html
```

Open the generated HTML file in any browser.

## Log format

Examples:

```text
2026-10-07 16:30:03 | FAILED | CURL_ERROR_56
2026-10-07 16:30:11 | OK | 343 ms | HTTP 200
```

`generate_latency_chart.py` only plots `OK` rows that include latency in `ms`.

## Notes

- HTTP 2xx/3xx responses are logged as `OK`; other HTTP statuses are logged as `HTTP_ERROR`.
- Curl execution failures are logged as `FAILED` with a categorized error (`TIMEOUT`, `DNS_FAILURE`, etc.).
