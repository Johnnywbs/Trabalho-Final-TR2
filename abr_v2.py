class BufferBasedABR:
    """
    Política 2: Buffer-Based ABR com dois estados explícitos.

    STARTUP (buffer < THRESH_LOW):
        Usa throughput com fator de segurança como teto — comportamento igual ao P1.
        Objetivo: encher o buffer rapidamente antes de ativar o controle por buffer.

    STEADY (buffer estabilizou ao menos uma vez):
        O buffer é o ÚNICO sinal de controle. Sem teto de throughput para subidas.
        Isso permite tentar qualidades maiores quando o buffer está cheio, usando-o
        como almofada — diferença fundamental em relação ao P1.

        Zonas de histerese:
            buf < 4s            → emergência: 240p imediato
            4s ≤ buf < 8s       → zona baixa: down_counter++
            8s ≤ buf < 12s      → zona estável: mantém qualidade
            buf ≥ 12s           → zona cheia: up_counter++

        Mudança de qualidade somente após HYSTERESIS=2 confirmações consecutivas.
        Se 720p drenar o buffer → down_counter atinge 2 → desce para 480p sozinho.
    """

    SAFETY           = 0.8   # usado somente no STARTUP
    THRESH_EMERGENCY = 4.0
    THRESH_LOW       = 8.0
    THRESH_HIGH      = 12.0
    HYSTERESIS       = 2

    def __init__(self, manifest):
        self.quality_levels = sorted(
            manifest["representations"],
            key=lambda r: r["bitrate_kbps"]
        )
        self.current_quality_idx = 0
        self.throughput_history  = []   # janela de 3 amostras para o STARTUP
        self.up_counter          = 0
        self.down_counter        = 0
        self._startup            = True  # True até buffer >= THRESH_LOW

    # ------------------------------------------------------------------

    def record_throughput(self, throughput_kbps: float):
        self.throughput_history.append(throughput_kbps)
        if len(self.throughput_history) > 3:
            self.throughput_history.pop(0)

    # ------------------------------------------------------------------

    def _safe_tput(self):
        if not self.throughput_history:
            return None
        return sum(self.throughput_history) / len(self.throughput_history) * self.SAFETY

    def _quality_by_tput(self) -> int:
        """Maior índice suportado pelo throughput seguro (usado somente no STARTUP)."""
        teto = self._safe_tput()
        if teto is None:
            return 0
        for i in range(len(self.quality_levels) - 1, -1, -1):
            if self.quality_levels[i]["bitrate_kbps"] <= teto:
                return i
        return 0

    # ------------------------------------------------------------------

    def get_next_quality(self, buffer_level_s: float = 0.0) -> str:
        n = len(self.quality_levels)

        # ── FASE STARTUP ────────────────────────────────────────────────
        if self._startup:
            idx = self._quality_by_tput()
            self.current_quality_idx = idx
            q   = self.quality_levels[idx]["quality"]
            br  = self.quality_levels[idx]["bitrate_kbps"]
            teto = self._safe_tput()
            teto_str = f"{teto:.0f}" if teto else "N/A"
            if buffer_level_s >= self.THRESH_LOW:
                self._startup = False
                print(f"[ABR-v2] STARTUP→STEADY buf={buffer_level_s:.1f}s "
                      f"teto={teto_str} kbps → {q} ({br} kbps)")
            else:
                print(f"[ABR-v2] STARTUP buf={buffer_level_s:.1f}s "
                      f"teto={teto_str} kbps → {q} ({br} kbps)")
            return q

        # ── FASE STEADY ─────────────────────────────────────────────────
        idx = self.current_quality_idx

        # Emergência: buffer criticamente baixo
        if buffer_level_s < self.THRESH_EMERGENCY:
            self.up_counter = self.down_counter = 0
            self.current_quality_idx = 0
            q = self.quality_levels[0]["quality"]
            print(f"[ABR-v2] EMERGÊNCIA buf={buffer_level_s:.1f}s → {q}")
            return q

        # Zonas de histerese — buffer é o único sinal de controle
        if buffer_level_s < self.THRESH_LOW:
            self.up_counter = 0
            self.down_counter += 1
        elif buffer_level_s >= self.THRESH_HIGH:
            self.down_counter = 0
            self.up_counter += 1
        else:
            self.up_counter = self.down_counter = 0

        if self.down_counter >= self.HYSTERESIS and idx > 0:
            idx -= 1
            self.down_counter = 0

        if self.up_counter >= self.HYSTERESIS and idx < n - 1:
            idx += 1
            self.up_counter = 0

        # Sem teto de throughput: o buffer controla a subida
        self.current_quality_idx = idx
        q  = self.quality_levels[idx]["quality"]
        br = self.quality_levels[idx]["bitrate_kbps"]
        print(
            f"[ABR-v2] STEADY buf={buffer_level_s:.1f}s "
            f"up={self.up_counter} down={self.down_counter} "
            f"→ {q} ({br} kbps)"
        )
        return q
