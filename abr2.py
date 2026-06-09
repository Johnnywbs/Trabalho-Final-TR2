def obter_bitrate(nivel):
    """Função simples para ordenar as qualidades pelo bitrate."""
    return nivel["bitrate_kbps"]

class PredictiveBufferABR:
    def __init__(self, manifest, min_buf_s=2.0, max_buf_s=3.5):
        # Limites reativos ajustados para reagir rápido nos 10 segmentos
        self.min_buf_s = min_buf_s
        self.max_buf_s = max_buf_s
        
        self.throughput_history = []
        self.last_buffer_s = 0.0
        
        self.quality_levels = sorted(manifest["representations"], key=obter_bitrate)
        self.current_index = 0

    def get_next_quality(self, current_buffer_s, last_throughput_kbps):
        # 1. Memória da rede (Média móvel dos últimos 3 downloads)
        if last_throughput_kbps > 0:
            self.throughput_history.append(last_throughput_kbps)
            if len(self.throughput_history) > 3:
                self.throughput_history.pop(0)

        safe_throughput = float('inf')
        if self.throughput_history:
            avg_throughput = sum(self.throughput_history) / len(self.throughput_history)
            safe_throughput = avg_throughput * 0.8  # Fator de segurança de 20%

        # 2. Verifica a tendência: O buffer está subindo ou descendo?
        buffer_crescendo = current_buffer_s >= self.last_buffer_s
        self.last_buffer_s = current_buffer_s

        print(f"[Pred-ABR] Buffer: {current_buffer_s:.2f}s | Rede Segura: {safe_throughput:.2f} kbps | Crescendo: {buffer_crescendo}")

        # 3. Decisão baseada no buffer e rede
        if current_buffer_s < self.min_buf_s:
            self.current_index = 0
            
        elif current_buffer_s > self.max_buf_s and buffer_crescendo:
            proximo_index = self.current_index + 1
            if proximo_index < len(self.quality_levels):
                if self.quality_levels[proximo_index]["bitrate_kbps"] <= safe_throughput:
                    self.current_index = proximo_index
                    
        elif not buffer_crescendo and current_buffer_s < (self.max_buf_s + 1.0):
            if self.current_index > 0:
                self.current_index -= 1

        selected_level = self.quality_levels[self.current_index]
        return selected_level["quality"]