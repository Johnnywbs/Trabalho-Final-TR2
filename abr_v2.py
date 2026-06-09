class BufferBasedABR:
    """
    Política 3.4: BBA Otimizado (Histerese Assimétrica + Safe Zone Estrita).
    Saída de log formatada para manter o padrão original.
    """

    RESERVOIR = 2.0        
    MAX_BUFFER_MAP = 12.0  
    
    SAFE_ZONE_MIN = 6.0    
    
    UP_TOLERANCE = 1       
    DOWN_TOLERANCE = 2     

    def __init__(self, manifest):
        self.quality_levels = sorted(
            manifest["representations"],
            key=lambda r: r["bitrate_kbps"]
        )
        self.min_bitrate = self.quality_levels[0]["bitrate_kbps"]
        self.max_bitrate = self.quality_levels[-1]["bitrate_kbps"]
        
        self.current_idx = 0
        self.up_counter = 0
        self.down_counter = 0

    def record_throughput(self, throughput_kbps: float):
        pass

    def get_next_quality(self, buffer_level_s: float = 0.0) -> str:
        # 1. Calcula o bitrate alvo pela fórmula linear
        if buffer_level_s <= self.RESERVOIR:
            target_bitrate = self.min_bitrate
        elif buffer_level_s >= self.MAX_BUFFER_MAP:
            target_bitrate = self.max_bitrate
        else:
            razao = (buffer_level_s - self.RESERVOIR) / (self.MAX_BUFFER_MAP - self.RESERVOIR)
            target_bitrate = self.min_bitrate + razao * (self.max_bitrate - self.min_bitrate)

        # 2. Descobre a sugestão pura da matemática
        raw_suggestion_idx = 0
        for i, level in enumerate(self.quality_levels):
            if level["bitrate_kbps"] <= target_bitrate:
                raw_suggestion_idx = i
            else:
                break

        # 3. Histerese com Trava de Segurança
        if buffer_level_s <= self.RESERVOIR:
            self.current_idx = raw_suggestion_idx
            self.up_counter = 0
            self.down_counter = 0
        else:
            if raw_suggestion_idx > self.current_idx:
                self.up_counter += 1
                self.down_counter = 0
                if self.up_counter >= self.UP_TOLERANCE:
                    self.current_idx = raw_suggestion_idx
                    self.up_counter = 0
            
            elif raw_suggestion_idx < self.current_idx:
                if buffer_level_s < self.SAFE_ZONE_MIN:
                    self.down_counter += 1
                    self.up_counter = 0
                    if self.down_counter >= self.DOWN_TOLERANCE:
                        self.current_idx -= 1
                        self.down_counter = 0
                else:
                    self.up_counter = 0
                    self.down_counter = 0
            
            else:
                self.up_counter = 0
                self.down_counter = 0

        # 4. Entrega com a formatação exigida
        selected_quality = self.quality_levels[self.current_idx]["quality"]
        selected_bitrate = self.quality_levels[self.current_idx]["bitrate_kbps"]
        
        # --- MUDANÇA AQUI: Formatação imitando o Rate-Based ---
        print(f"[ABR] Buffer level: {buffer_level_s:.2f}s | Target bitrate: {target_bitrate:.2f} kbps")
        print(f"[ABR] Selected quality: {selected_quality} (Requires {selected_bitrate} kbps)")
        
        return selected_quality
