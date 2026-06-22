# =============================================================================
# Política 3 — EWMA-Based ABR com Penalidade de Jitter e Bônus de Buffer
# =============================================================================
# Usa a Média Móvel Exponencial (EWMA) do throughput como sinal principal para
# estimar a capacidade da rede e escolher a qualidade do próximo segmento.
#
# Diferença fundamental em relação às outras políticas:
#   P1: usa média simples dos últimos 3 segmentos × fator fixo (0.8)
#   P2: ignora a rede — decide só pelo nível do buffer
#   P3: usa EWMA × fator de segurança, com penalidade de jitter e bônus de buffer
#
# Componentes:
#   1. EWMA de vazão (α = 0.4):
#      EWMA_nova = 0.4 × vazão_atual + 0.6 × EWMA_anterior
#      Alpha maior que P1 → reage mais rápido a mudanças reais de rede,
#      mas sem supervalorizar picos pontuais como a leitura instantânea.
#
#   2. Penalidade de jitter (ativa somente com buffer < ZONA_SEGURA_MIN):
#      Jitter alto indica entrega irregular dos chunks — o intervalo entre
#      chegadas oscila, o que pode esgotar o buffer antes do próximo segmento
#      mesmo com throughput médio aparentemente suficiente.
#      Com buffer baixo, esse risco é imediato: a penalidade reduz o fator de
#      segurança proporcionalmente ao jitter, forçando um bitrate menor que
#      baixa mais rápido e reabastece o buffer antes de um rebuffer.
#      Com buffer alto (>= ZONA_SEGURA_MIN), a penalidade é desativada —
#      o buffer já absorve a irregularidade sem precisar reduzir qualidade.
#      fator = max(0.70, FATOR_SEGURANCA − excesso/LIMIAR × PENALIDADE)
#
#   3. Bônus de buffer (buffer >= BUFFER_BONUS_S = 10s):
#      Com buffer confortável, sugere um nível acima do atual independente da
#      EWMA. O buffer acumulado é a margem de segurança que permite arriscar
#      um segmento mais pesado. A histerese confirma a subida.
#
#   4. Histerese simétrica (1 confirmação para subir e descer):
#      Evita oscilações em ambas as direções sem tornar a política lenta.
# =============================================================================

ALPHA_EWMA_VAZAO  = 0.4   # peso da amostra mais recente
ALPHA_EWMA_JITTER = 0.3   # suaviza spikes pontuais de jitter


class HybridStatisticalABR:

    FATOR_SEGURANCA  = 0.99  # usa 99% da EWMA — margem para variações pontuais
    LIMIAR_JITTER_MS = 25.0  # jitter abaixo disto não penaliza
    PENALIDADE_JITTER = 0.10 # reduz o fator em 10% por múltiplo do limiar

    RESERVATORIO    = 2.0    # abaixo: emergência, força qualidade mínima
    ZONA_SEGURA_MIN = 8.0    # abaixo: penalidade de jitter ativa
    BUFFER_BONUS_S  = 12.0   # acima: sugere um nível além da EWMA

    TOLERANCIA  = 2

    def __init__(self, manifest):
        self.niveis = sorted(
            manifest["representations"],
            key=lambda r: r["bitrate_kbps"]
        )

        self.idx_atual    = 0
        self.cont_subida  = 0
        self.cont_descida = 0

        self.ewma_vazao     = None
        self.jitter_ewma_ms = 0.0

    def registrar_vazao(self, vazao_kbps, jitter_ms=0.0):
        """Atualiza a EWMA de vazão e a EWMA de jitter."""
        if self.ewma_vazao is None:
            self.ewma_vazao = vazao_kbps
        else:
            self.ewma_vazao = (ALPHA_EWMA_VAZAO * vazao_kbps
                               + (1 - ALPHA_EWMA_VAZAO) * self.ewma_vazao)

        self.jitter_ewma_ms = (ALPHA_EWMA_JITTER * jitter_ms
                               + (1 - ALPHA_EWMA_JITTER) * self.jitter_ewma_ms)

    def proxima_qualidade(self, buffer_level_s=0.0):
        """Retorna o rótulo de qualidade escolhido para o próximo segmento."""
        minima = self.niveis[0]

        # --- Emergência: buffer crítico força qualidade mínima ---
        if buffer_level_s < self.RESERVATORIO:
            self.idx_atual    = 0
            self.cont_subida  = 0
            self.cont_descida = 0
            print(f"[ABR P3] Buffer crítico ({buffer_level_s:.2f}s)"
                  f" — forçando qualidade mínima: {minima['quality']}")
            return minima["quality"]

        # ---- Penalidade de jitter (só com buffer baixo) ----
        # Com buffer baixo, jitter alto pode esgotar o buffer antes do próximo
        # segmento chegar. A penalidade antecipa a redução de qualidade.
        # Com buffer alto, o buffer já absorve a irregularidade — sem penalidade.
        if buffer_level_s < self.ZONA_SEGURA_MIN:
            excesso  = max(0.0, self.jitter_ewma_ms - self.LIMIAR_JITTER_MS)
            multiplo = excesso / self.LIMIAR_JITTER_MS
            fator    = max(0.70, self.FATOR_SEGURANCA
                           - multiplo * self.PENALIDADE_JITTER)
        else:
            fator = self.FATOR_SEGURANCA

        # ---- Estimativa de capacidade da rede ----
        estimativa = self.ewma_vazao * fator

        # ---- Seleção de qualidade pela estimativa ----
        idx_sugerido = 0
        for i, nivel in enumerate(self.niveis):
            if nivel["bitrate_kbps"] <= estimativa:
                idx_sugerido = i

        # ---- Bônus de buffer: sugere um nível acima do atual ----
        # Com buffer >= BUFFER_BONUS_S o player tem reserva para absorver um
        # segmento mais pesado. Substitui o idx_sugerido pela estimativa.
        if buffer_level_s >= self.BUFFER_BONUS_S:
            idx_sugerido = min(len(self.niveis) - 1, self.idx_atual + 1)

        # ---- Histerese simétrica (2 confirmações para subir e descer) ----
        if idx_sugerido > self.idx_atual:
            self.cont_subida  += 1
            self.cont_descida  = 0
            if self.cont_subida >= self.TOLERANCIA:
                self.idx_atual   = idx_sugerido
                self.cont_subida = 0

        elif idx_sugerido < self.idx_atual:
            # Descida bloqueada quando buffer está confortável — o buffer acumulado
            # absorve a variação temporária sem precisar reduzir qualidade.
            if buffer_level_s >= self.ZONA_SEGURA_MIN:
                self.cont_subida  = 0
                self.cont_descida = 0
            else:
                self.cont_descida += 1
                self.cont_subida   = 0
                if self.cont_descida >= self.TOLERANCIA:
                    self.idx_atual   -= 1
                    self.cont_descida = 0
        else:
            self.cont_subida  = 0
            self.cont_descida = 0

        qualidade = self.niveis[self.idx_atual]["quality"]
        bitrate   = self.niveis[self.idx_atual]["bitrate_kbps"]
        bonus_str  = " | Bônus buffer ativo" if buffer_level_s >= self.BUFFER_BONUS_S else ""
        jitter_str = (f" | Jitter: {self.jitter_ewma_ms:.1f} ms → fator={fator:.2f}"
                      if buffer_level_s < self.ZONA_SEGURA_MIN else "")

        print(f"[ABR P3] EWMA: {self.ewma_vazao:.0f} kbps × {fator:.2f}"
              f" = {estimativa:.0f} kbps"
              f" | Buffer: {buffer_level_s:.2f}s{jitter_str}{bonus_str}")
        print(f"[ABR P3] Qualidade escolhida: {qualidade} (requer {bitrate} kbps)")
        return qualidade

    # ------------------------------------------------------------------
    # Aliases para compatibilidade com main.py (interface unificada)
    # ------------------------------------------------------------------
    def record_throughput(self, throughput_kbps, jitter_ms=0.0):
        self.registrar_vazao(throughput_kbps, jitter_ms)

    def get_next_quality(self, buffer_level_s=0.0):
        return self.proxima_qualidade(buffer_level_s)
