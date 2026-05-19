class BufferManager:
    def __init__(self):
        # Começamos o vídeo com o buffer zerado
        self.buffer_level_s = 0.0
        
        # Estatísticas para o seu relatório final (você vai precisar disso no CSV)
        self.total_rebuffer_events = 0
        self.total_stall_duration_s = 0.0

    def atualizar_buffer(self, tempo_download_s, duracao_segmento_s):
        """
        Atualiza o nível do buffer após o download de um segmento.
        Retorna informações vitais para salvar no CSV.
        
        :param tempo_download_s: O tempo real que levou para baixar o segmento (em segundos).
        :param duracao_segmento_s: Quantos segundos de vídeo o segmento contém (ex: 4.0s).
        :return: (buffer_can_play, rebuffer_event, stall_duration_s)
        """
        
        rebuffer_event = 0
        stall_duration_s = 0.0
        
        # 1. O vídeo estava tocando ENQUANTO baixávamos. 
        # Portanto, consumimos uma parte do nosso buffer equivalente ao tempo do download.
        self.buffer_level_s -= tempo_download_s
        
        # 2. O buffer esgotou durante o download? (Ficou menor que zero)
        if self.buffer_level_s < 0:
            # Sim! O vídeo travou. 
            rebuffer_event = 1
            
            # O tempo que a tela ficou congelada é o valor que faltou (transformado em positivo)
            stall_duration_s = abs(self.buffer_level_s)
            
            # Atualiza as estatísticas globais
            self.total_rebuffer_events += 1
            self.total_stall_duration_s += stall_duration_s
            
            # Na vida real, não existe "buffer negativo". Ele simplesmente zera e o vídeo para.
            self.buffer_level_s = 0.0
            
            # Como o buffer zerou antes do download terminar, ele NÃO foi suficiente para continuous play
            buffer_can_play = 0
        else:
            # O download foi rápido o suficiente! Sobrou buffer, o vídeo não travou.
            buffer_can_play = 1

        # 3. Finalmente, o download acabou. Ganhamos os segundos do novo segmento!
        self.buffer_level_s += duracao_segmento_s
        
        # Imprime o status atual para facilitar o acompanhamento no terminal
        status_rebuffer = "⚠️ TRAVOU!" if rebuffer_event else "✅ Fluido"
        print(f"[Buffer] Nível atual: {self.buffer_level_s:.2f}s | {status_rebuffer} "
              f"(Stall: {stall_duration_s:.2f}s)")

        return buffer_can_play, rebuffer_event, stall_duration_s

    def get_nivel_atual(self):
        """Retorna o nível atual do buffer em segundos."""
        return self.buffer_level_s