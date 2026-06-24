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

    def record_throughput(self, throughput_kbps, _jitter_ms=0.0):
        self.throughput_history.append(throughput_kbps)
        if len(self.throughput_history) > self.window_size:
            self.throughput_history.pop(0)

    def get_next_quality(self, buffer_level_s=0.0):
        if not self.throughput_history:
            lowest_quality = self.quality_levels[-1]
            print(f"[ABR P1] Sem histórico. Iniciando na qualidade mínima: {lowest_quality['quality']}")
            return lowest_quality["quality"]

        average_throughput = sum(self.throughput_history) / len(self.throughput_history)
        safe_throughput = average_throughput * self.safety_factor

        print(f"[ABR P1] Média recente: {average_throughput:.2f} kbps | Vazão segura: {safe_throughput:.2f} kbps")

        for level in self.quality_levels:
            if level["bitrate_kbps"] <= safe_throughput:
                print(f"[ABR P1] Qualidade escolhida: {level['quality']} (requer {level['bitrate_kbps']} kbps)")
                return level["quality"]

        lowest_quality = self.quality_levels[-1]
        print(f"[ABR P1] Banda crítica! Forçando qualidade mínima: {lowest_quality['quality']}")
        return lowest_quality["quality"]