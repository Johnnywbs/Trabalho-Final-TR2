import urllib.request
import json
import urllib.error
import time

class StreamingClient:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.manifest_data = None

    def fetch_manifest(self):
        print(f"Fetching manifest from: {self.manifest_url}")
        try:
            with urllib.request.urlopen(self.manifest_url) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    self.manifest_data = json.loads(data)
                    print("Manifest loaded successfully!\n")
                    return self.manifest_data
                else:
                    print(f"Error: Server returned status {response.status}")
                    return None
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return None

    def download_segment(self, segment_url):
        start_time = time.time()

        try:
            with urllib.request.urlopen(segment_url) as response:
                if response.status == 200:
                    segment_data = response.read()
                    end_time = time.time()

                    size_bytes = len(segment_data)
                    download_time_s = max(end_time - start_time, 0.001)
                    throughput_kbps = (size_bytes * 8 / 1000) / download_time_s

                    print(f"Segment downloaded! "
                          f"Size: {size_bytes} bytes | "
                          f"Time: {download_time_s:.3f}s | "
                          f"Throughput: {throughput_kbps:.2f} kbps")

                    return size_bytes, download_time_s, throughput_kbps

                else:
                    print(f"Error downloading segment: HTTP {response.status}")
                    return 0, 0, 0

        except urllib.error.URLError as e:
            print(f"Network error downloading segment: {e}")
            return 0, 0, 0
