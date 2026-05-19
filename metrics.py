import csv
from datetime import datetime

class MetricsLogger:
    def __init__(self, filename="streaming_metrics.csv"):
        self.filename = filename
        self._write_header()

    def _write_header(self):
        headers = [
            "segment", "timestamp", "server_id", "quality", "bitrate_kbps",
            "throughput_kbps", "download_time_s", "jitter_network_ms",
            "jitter_ewma_ms", "buffer_level_s", "buffer_can_play",
            "rebuffer_event", "stall_duration_s", "failover_total"
        ]
        with open(self.filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)

    def log_segment(self, segment_data):
        row = [
            segment_data.get("segment", 0),
            datetime.now().isoformat(),
            segment_data.get("server_id", "A"),
            segment_data.get("quality", "Unknown"),
            segment_data.get("bitrate_kbps", 0),
            round(segment_data.get("throughput_kbps", 0.0), 2),
            round(segment_data.get("download_time_s", 0.0), 3),
            round(segment_data.get("jitter_network_ms", 0.0), 2),
            round(segment_data.get("jitter_ewma_ms", 0.0), 2),
            round(segment_data.get("buffer_level_s", 0.0), 2),
            segment_data.get("buffer_can_play", 0),
            segment_data.get("rebuffer_event", 0),
            round(segment_data.get("stall_duration_s", 0.0), 2),
            segment_data.get("failover_total", 0)
        ]
        with open(self.filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(row)
