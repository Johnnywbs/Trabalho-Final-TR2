# Adaptive Bitrate Streaming Client

A Python simulation of an ABR (Adaptive Bitrate) streaming client. The client downloads video segments from a server, dynamically adjusting the quality level based on real-time network conditions, while tracking buffer state and logging performance metrics.

---

## Project Structure

```
trabalhoFinal/
├── main.py             # Entry point — orchestrates the full streaming loop
├── client.py           # HTTP client for fetching the manifest and downloading segments
├── abr.py              # ABR algorithm — decides quality level for each segment
├── buffer_manager.py   # Simulates the video playback buffer
├── metrics.py          # Logs per-segment metrics to a CSV file
└── plot.py             # Generates a chart from the CSV data
```

---

## How It Works

The client simulates what a real video player does when streaming: it continuously downloads video segments one by one, deciding on-the-fly whether to stream at high quality (when the connection is fast) or drop to a lower quality (when the connection is slow), all while trying to avoid the buffer from running out and causing the video to freeze.

### Step-by-Step Flow

```
1. Fetch manifest        → learn available quality levels and server URL
2. For each segment:
   a. ABR decides quality → based on recent measured throughput
   b. Download segment    → measure actual download time and throughput
   c. Update ABR history  → feed new throughput into the sliding window
   d. Update buffer       → simulate how the buffer level changes
   e. Log metrics         → write a row to the CSV
3. Generate chart         → visualize throughput vs. quality over time
```

---

## Modules in Detail

### `main.py` — Orchestrator

The entry point. Instantiates all components and runs the segment download loop.

**Key constants:**
| Constant | Value | Description |
|---|---|---|
| `MANIFEST_URL` | `http://…:8080/manifest` | Address of the streaming server manifest |
| `TOTAL_SEGMENTS` | `10` | Number of segments to download |
| `SEGMENT_DURATION_S` | read from manifest (default `2.0`) | Duration of each video segment in seconds |

**Loop logic per segment:**
1. Ask the ABR for the best quality → `abr.get_next_quality()`
2. Look up the download URL for that quality in the manifest
3. Download the segment → `client.download_segment(segment_url)`
4. Report the measured throughput back to ABR → `abr.record_throughput()`
5. Update the buffer simulation → `buffer.update_buffer()`
6. Write all metrics for this segment to the CSV → `logger.log_segment()`

---

### `client.py` — HTTP Client (`StreamingClient`)

Handles all network communication using Python's built-in `urllib`.

#### `fetch_manifest()`
Performs a GET request to `MANIFEST_URL` and parses the JSON response. The manifest describes the available quality representations and the server base URL. Expected structure:

```json
{
  "segment_duration_s": 2.0,
  "servers": [{ "url": "http://....:8080" }],
  "representations": [
    { "quality": "1080p", "bitrate_kbps": 4500, "url_path": "/segment/1080p" },
    { "quality": "720p",  "bitrate_kbps": 2500, "url_path": "/segment/720p"  },
    { "quality": "480p",  "bitrate_kbps": 1000, "url_path": "/segment/480p"  },
    { "quality": "240p",  "bitrate_kbps": 400,  "url_path": "/segment/240p"  }
  ]
}
```

#### `download_segment(segment_url)`
Downloads one segment and measures network performance:

```
throughput (kbps) = (size_bytes × 8 / 1000) / download_time_s
```

A floor of `0.001s` is applied to `download_time_s` to prevent division by zero on extremely fast local connections.

Returns `(size_bytes, download_time_s, throughput_kbps)`.

---

### `abr.py` — Adaptive Bitrate Algorithm (`RateBasedABR`)

Implements a **Rate-Based ABR** algorithm. The goal is to always choose the highest quality whose required bitrate fits comfortably within the current estimated network capacity.

#### Parameters
| Parameter | Default | Description |
|---|---|---|
| `safety_factor` | `0.8` | Multiplier applied to the average throughput to create a safety margin (80%) |
| `window_size` | `3` | Number of recent segments kept in the throughput history |

#### `record_throughput(throughput_kbps)`
Appends the latest measurement to a sliding window. Once the window exceeds `window_size`, the oldest entry is dropped. This means the ABR reacts quickly to network changes without being affected by a single outlier.

#### `get_next_quality()`
Decision logic:

```
1. If no history yet → return the lowest quality (safe default)
2. Compute the average of the sliding window
3. Apply the safety margin:  safe_throughput = average × safety_factor
4. Iterate quality levels from highest to lowest bitrate
5. Return the first level whose bitrate_kbps ≤ safe_throughput
6. If none fit → return the lowest quality (last resort)
```

The safety factor (0.8) means the algorithm only picks a quality whose bitrate uses at most 80% of the estimated capacity, leaving headroom for throughput fluctuations.

**Example:**

```
Recent throughput: [3000, 2800, 3200] kbps
Average:           3000 kbps
Safe throughput:   2400 kbps  (3000 × 0.8)
Quality chosen:    720p       (requires 2500 kbps? No. 480p requires 1000 kbps? Yes → 480p)
```

---

### `buffer_manager.py` — Buffer Simulation (`BufferManager`)

Models the playback buffer — the pool of pre-downloaded video content that keeps the player running smoothly even if the network hiccups briefly.

#### State
| Attribute | Description |
|---|---|
| `buffer_level_s` | Current buffer depth in seconds of video |
| `total_rebuffer_events` | Total number of stall events across the session |
| `total_stall_duration_s` | Cumulative freeze time in seconds |

#### `update_buffer(download_time_s, segment_duration_s)`

The core of the simulation. It models two simultaneous events that happen during every segment download:

```
Phase 1 — Consumption:
  While downloading takes download_time_s, the player keeps playing.
  buffer_level -= download_time_s

Phase 2 — Stall check:
  If buffer_level < 0:
    → Video froze. stall_duration = abs(buffer_level)
    → buffer_level reset to 0

Phase 3 — Replenishment:
  Download is complete. New content added.
  buffer_level += segment_duration_s
```

Returns `(buffer_can_play, rebuffer_event, stall_duration_s)`.

**Scenario A — Fast network (no stall):**
```
buffer before: 4.0s
download_time: 0.5s  → buffer drops to 3.5s  (no stall)
segment adds:  2.0s  → buffer rises to 5.5s
```

**Scenario B — Slow network (stall):**
```
buffer before: 1.0s
download_time: 3.0s  → buffer drops to -2.0s  (froze for 2.0s!)
stall_duration: 2.0s, buffer reset to 0.0s
segment adds:  2.0s  → buffer rises to 2.0s
```

---

### `metrics.py` — CSV Logger (`MetricsLogger`)

Writes one row per segment to `streaming_metrics.csv`. The file is (re)created fresh each time the client starts.

#### CSV Columns

| Column | Type | Description |
|---|---|---|
| `segment` | int | Segment sequence number (1, 2, 3, …) |
| `timestamp` | ISO 8601 string | Wall-clock time when the segment was logged |
| `server_id` | string | Server identifier (default `"A"`) |
| `quality` | string | Quality label chosen by ABR (e.g. `"720p"`) |
| `bitrate_kbps` | int | Nominal bitrate of the chosen quality |
| `throughput_kbps` | float | Actual measured network throughput |
| `download_time_s` | float | Time taken to download the segment |
| `jitter_network_ms` | float | Per-segment network jitter (reserved, default `0`) |
| `jitter_ewma_ms` | float | EWMA-smoothed jitter (reserved, default `0`) |
| `buffer_level_s` | float | Buffer depth after the segment was processed |
| `buffer_can_play` | int | `1` if playback was continuous, `0` if it stalled |
| `rebuffer_event` | int | `1` if a stall occurred during this segment |
| `stall_duration_s` | float | Duration of the stall in seconds (`0` if none) |
| `failover_total` | int | Number of server failovers (reserved, default `0`) |

---

### `plot.py` — Chart Generator

Reads `streaming_metrics.csv` and produces a dual-line chart saved as `baseline_chart.png`.

- **Blue dashed line** — actual network throughput per segment
- **Orange step line** — quality level (bitrate) chosen by the ABR per segment
- **Labels** — quality name (e.g. `480p`) annotated above each orange point

The step chart (`plt.step`) is intentional: quality does not ramp smoothly — it jumps abruptly from one level to another between segments.

---

## Output Files

| File | Generated by | Description |
|---|---|---|
| `streaming_metrics.csv` | `MetricsLogger` | Per-segment performance log |
| `baseline_chart.png` | `plot.py` | Throughput vs. quality visualization |

---

## Running the Project

```bash
python main.py
```

This will:
1. Fetch the manifest from the server
2. Download 10 segments, printing progress to the terminal
3. Save `streaming_metrics.csv`
4. Generate and display `baseline_chart.png`

To regenerate the chart from an existing CSV without re-downloading:

```bash
python plot.py
```

---

## Dependencies

| Library | Used in | Purpose |
|---|---|---|
| `urllib` | `client.py` | HTTP requests (standard library) |
| `csv` | `metrics.py`, `plot.py` | CSV read/write (standard library) |
| `datetime` | `metrics.py` | ISO 8601 timestamps (standard library) |
| `matplotlib` | `plot.py` | Chart generation (third-party) |

Install third-party dependencies:

```bash
pip install matplotlib
```
