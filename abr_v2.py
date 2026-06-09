def obter_bitrate(nivel):
    return nivel["bitrate_kbps"]

class BufferBasedABR:
    def __init__(self, manifest, buffer_manager, panic_buf=2.0, down_buf=3.0, up_buf=5.0):
        self.buffer_manager = buffer_manager
        self.throughput_history = []
        
        self.quality_levels = sorted(manifest["representations"], key=obter_bitrate)
        self.current_index = 0 
        
        # Parâmetros de Sensibilidade 
        self.panic_buf_s = panic_buf  # Limite crítico: Corta para 240p imediatamente
        self.down_buf_s = down_buf    # Limite de alerta: Desce 1 degrau suavemente
        self.up_buf_s = up_buf        # Limite de conforto: Sobe 1 degrau

    def record_throughput(self, throughput_kbps):
        self.throughput_history.append(throughput_kbps)
        if len(self.throughput_history) > 3:
            self.throughput_history.pop(0)

    def get_next_quality(self):
        current_buffer = self.buffer_manager.get_current_level()
        
        safe_throughput = float('inf')
        if self.throughput_history:
            avg_throughput = sum(self.throughput_history) / len(self.throughput_history)
            safe_throughput = avg_throughput * 0.8
            
        # ZONA 1: Pânico (Buffer quase vazio)
        if current_buffer <= self.panic_buf_s:
            self.current_index = 0
            
        # ZONA 2: Conforto (Buffer grande o suficiente para arriscar subir)
        elif current_buffer >= self.up_buf_s:
            proximo_index = self.current_index + 1
            if proximo_index < len(self.quality_levels):
                bitrate_exigido = self.quality_levels[proximo_index]["bitrate_kbps"]
                if bitrate_exigido <= safe_throughput:
                    self.current_index = proximo_index
                    
        # ZONA 3: Alerta (Buffer caindo)
        elif current_buffer < self.down_buf_s and self.current_index > 0:
            self.current_index -= 1

        selected_level = self.quality_levels[self.current_index]
        return selected_level["quality"]