def obter_bitrate(level):
    """Função auxiliar para ordenar as qualidades pelo bitrate."""
    return level["bitrate_kbps"]

class RateBasedABR:
    def __init__(self, manifest, safety_factor=0.8, window_size=3):
        self.safety_factor = safety_factor
        self.window_size = window_size
        self.throughput_history = []

        # Ordena do maior bitrate para o menor (descrescente)
        self.quality_levels = sorted(
            manifest["representations"],
            key=obter_bitrate,
            reverse=True
        )

    def record_throughput(self, throughput_kbps):
        self.throughput_history.append(throughput_kbps)
        if len(self.throughput_history) > self.window_size:
            self.throughput_history.pop(0)

    def get_next_quality(self, current_buffer_s=0.0):
        if not self.throughput_history:
            lowest_quality = self.quality_levels[-1]
            return lowest_quality["quality"]

        average_throughput = sum(self.throughput_history) / len(self.throughput_history)
        safe_throughput = average_throughput * self.safety_factor

        for level in self.quality_levels:
            if level["bitrate_kbps"] <= safe_throughput:
                return level["quality"]

        lowest_quality = self.quality_levels[-1]
        return lowest_quality["quality"]


class BufferBasedABR:
    """
    Política 2: Decide a qualidade baseada exclusivamente no tamanho do buffer.
    Evita oscilações rápidas de rede usando limites de histerese.
    """
    def __init__(self, manifest, min_buf_s=4.0, max_buf_s=10.0):
        self.min_buf_s = min_buf_s
        self.max_buf_s = max_buf_s
        
        # Ordena do menor para o maior bitrate (crescente)
        self.quality_levels = sorted(
            manifest["representations"],
            key=obter_bitrate
        )
        self.current_quality_idx = 0  # Começa na menor qualidade (Slow-start seguro)

    def get_next_quality(self, current_buffer_s):
        # Se o buffer estiver perigosamente baixo, reduz para a qualidade mínima
        if current_buffer_s < self.min_buf_s:
            self.current_quality_idx = 0
            
        # Se o buffer estiver bem cheio, tenta subir um degrau de qualidade
        elif current_buffer_s > self.max_buf_s:
            if self.current_quality_idx < len(self.quality_levels) - 1:
                self.current_quality_idx += 1
                
        # Se estiver no meio do caminho, mantém a qualidade estável anterior

        selected_level = self.quality_levels[self.current_quality_idx]
        print(f"[ABR-BBA] Buffer: {current_buffer_s:.2f}s | Qualidade: {selected_level['quality']}")
        return selected_level["quality"]