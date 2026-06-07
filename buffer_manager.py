import time

BUFFER_MAX_S    = 20.0
BUFFER_RESUME_S = 15.0   # limiar de retomada após pausa


class BufferManager:
    def __init__(self):
        self.buffer_level_s         = 0.0   # nível atual do buffer (segundos)
        self.total_rebuffer_events  = 0     # total de stalls na sessão
        self.total_stall_duration_s = 0.0   # soma de todos os tempos de stall
        self.total_pause_time_s     = 0.0   # tempo total pausado por buffer cheio

    def should_pause(self) -> bool:
        """
        Retorna True se o buffer está cheio e o download deve ser pausado.
        O laço principal deve chamar isso ANTES de iniciar o próximo download.
        """
        return self.buffer_level_s >= BUFFER_MAX_S

    def wait_until_resumable(self, segment_duration_s: float):
        """
        Simula a espera até o buffer baixar para BUFFER_RESUME_S.
        Parâmetros:
            segment_duration_s – duração de cada segmento (para log)
        """

        excesso = self.buffer_level_s - BUFFER_RESUME_S
        if excesso <= 0:
            return  # nada a fazer

        print(f"[Buffer] 🔴 Buffer cheio ({self.buffer_level_s:.1f}s ≥ {BUFFER_MAX_S}s). "
              f"Pausando download por {excesso:.1f}s …")

        inicio_pausa = time.time()
        time.sleep(excesso)           # aguarda o buffer "consumir" até o limiar
        tempo_pausado = time.time() - inicio_pausa

        self.buffer_level_s  = BUFFER_RESUME_S   # reflete o consumo simulado
        self.total_pause_time_s += tempo_pausado

        print(f"[Buffer] ▶️  Retomando. Buffer: {self.buffer_level_s:.1f}s "
              f"(pausado por {tempo_pausado:.1f}s)")

    # ------------------------------------------------------------------

    def update_buffer(self, download_time_s: float, segment_duration_s: float):
        """
        Deve ser chamado uma vez após cada segmento baixado.
        Parâmetros:
            download_time_s    – tempo real gasto no download (segundos)
            segment_duration_s – duração do conteúdo do segmento (segundos)
        """
        rebuffer_event   = 0
        stall_duration_s = 0.0
        self.buffer_level_s -= download_time_s

        if self.buffer_level_s < 0:
            # Buffer zerou antes do segmento chegar → stall de reprodução
            rebuffer_event       = 1
            stall_duration_s     = abs(self.buffer_level_s)
            self.total_rebuffer_events  += 1
            self.total_stall_duration_s += stall_duration_s
            self.buffer_level_s  = 0.0   # não pode ser negativo
            buffer_can_play      = 0
        else:
            buffer_can_play = 1

        # Adiciona o conteúdo do novo segmento ao buffer
        self.buffer_level_s += segment_duration_s

        # Aplica o teto (não deve ser atingido se should_pause() for usado corretamente,
        # mas funciona como salvaguarda)
        self.buffer_level_s = min(self.buffer_level_s, BUFFER_MAX_S)

        status = "STALL ⚠️" if rebuffer_event else "Normal ✅"
        print(f"[Buffer] Nível: {self.buffer_level_s:.2f}s | {status} "
              f"(stall: {stall_duration_s:.2f}s)")

        return buffer_can_play, rebuffer_event, stall_duration_s

    # ------------------------------------------------------------------

    def get_current_level(self) -> float:
        """Retorna o nível atual do buffer em segundos."""
        return self.buffer_level_s

    def summary(self) -> str:
        """Resumo da sessão para exibição ao final do streaming."""
        return (f"Rebuffers: {self.total_rebuffer_events} | "
                f"Stall total: {self.total_stall_duration_s:.2f}s | "
                f"Pausa por buffer cheio: {self.total_pause_time_s:.2f}s")