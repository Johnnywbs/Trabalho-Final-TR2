class RateBasedABR:
    def __init__(self, manifest, safety_factor=0.8, window_size=3):
        self.safety_factor = safety_factor
        self.window_size = window_size
        self.throughput_history = []

        self.quality_levels = sorted(
            manifest["representations"],
            key=lambda level: level["bitrate_kbps"],
            reverse=True
        )

    def record_throughput(self, throughput_kbps):
        self.throughput_history.append(throughput_kbps)
        if len(self.throughput_history) > self.window_size:
            self.throughput_history.pop(0)

    def get_next_quality(self):
        if not self.throughput_history:
            lowest_quality = self.quality_levels[-1]
            print(f"[ABR] No history. Starting at lowest quality: {lowest_quality['quality']}")
            return lowest_quality["quality"]

        average_throughput = sum(self.throughput_history) / len(self.throughput_history)
        safe_throughput = average_throughput * self.safety_factor

        print(f"[ABR] Recent average: {average_throughput:.2f} kbps | Safe throughput: {safe_throughput:.2f} kbps")

        for level in self.quality_levels:
            if level["bitrate_kbps"] <= safe_throughput:
                print(f"[ABR] Selected quality: {level['quality']} (Requires {level['bitrate_kbps']} kbps)")
                return level["quality"]

        lowest_quality = self.quality_levels[-1]
        print(f"[ABR] Critical bandwidth! Forcing minimum quality: {lowest_quality['quality']}")
        return lowest_quality["quality"]
