import time
from client import StreamingClient
from abr import RateBasedABR
from buffer_manager import BufferManager
from metrics import MetricsLogger
import plot

def run_client():
    MANIFEST_URL = "http://137.131.178.229:8080/manifest"
    TOTAL_SEGMENTS = 10

    client = StreamingClient(MANIFEST_URL)
    manifest = client.fetch_manifest()

    if not manifest:
        print("Failed to load manifest. Exiting.")
        return

    SEGMENT_DURATION_S = manifest.get("segment_duration_s", 2.0)

    abr = RateBasedABR(manifest)
    buffer = BufferManager()
    logger = MetricsLogger("streaming_metrics.csv")

    server_url = manifest["servers"][0]["url"]

    print("\n" + "="*50)
    print("STARTING STREAMING (BASELINE RATE-BASED)")
    print("="*50 + "\n")

    for segment_number in range(1, TOTAL_SEGMENTS + 1):
        print(f"--- Requesting Segment {segment_number} ---")

        selected_quality = abr.get_next_quality()

        selected_rep = next(r for r in manifest["representations"] if r["quality"] == selected_quality)
        nominal_bitrate = selected_rep["bitrate_kbps"]
        url_path = selected_rep["url_path"]

        segment_url = f"{server_url}{url_path}"

        size, download_time_s, throughput_kbps = client.download_segment(segment_url)

        abr.record_throughput(throughput_kbps)
        buffer_can_play, rebuffer_event, stall_duration_s = buffer.update_buffer(download_time_s, SEGMENT_DURATION_S)

        segment_data = {
            "segment": segment_number,
            "quality": selected_quality,
            "bitrate_kbps": nominal_bitrate,
            "throughput_kbps": throughput_kbps,
            "download_time_s": download_time_s,
            "buffer_level_s": buffer.get_current_level(),
            "buffer_can_play": buffer_can_play,
            "rebuffer_event": rebuffer_event,
            "stall_duration_s": stall_duration_s
        }
        logger.log_segment(segment_data)
        time.sleep(0.5)

    print("\nStreaming complete! CSV file generated.")

if __name__ == "__main__":
    run_client()

    print("Generating charts...")
    plot.generate_throughput_quality_chart("streaming_metrics.csv")
