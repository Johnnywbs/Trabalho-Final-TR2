"""
main.py  –  Orquestrador do cliente de streaming (Tarefa 2)

Uso:
    python main.py [--policy {1,2}] [--segments N]

    --policy 1   Rate-Based baseline  (padrão)
    --policy 2   Buffer-Based ABR     (implementado em abr_v2.py pela Parte 1)
    --segments N número de segmentos a baixar (padrão: 20)
"""

import argparse
import time

from client         import StreamingClient
from abr            import RateBasedABR
from buffer_manager import BufferManager
from metrics        import MetricsLogger
import plot

# ---------------------------------------------------------------------------
# Parâmetro da EWMA de jitter entre segmentos
# ---------------------------------------------------------------------------
JITTER_EWMA_ALPHA = 0.2

def atualizar_ewma(valor_anterior: float, novo_valor: float,
                   alpha: float = JITTER_EWMA_ALPHA) -> float:
    """Passo de atualização da Média Móvel Exponencial Ponderada (EWMA)."""
    return alpha * novo_valor + (1 - alpha) * valor_anterior


# ---------------------------------------------------------------------------
# Laço principal
# ---------------------------------------------------------------------------

def run_client(policy: int = 1, total_segments: int = 20):

    # ── Carrega o manifest ───────────────────────────────────────────────────
    # StreamingClient não recebe mais uma URL hardcoded.
    # Ele tenta cada servidor de KNOWN_SERVERS em ordem até um responder,
    # garantindo que o cliente funcione mesmo se o servidor A estiver fora.
    client   = StreamingClient()
    manifest = client.fetch_manifest()

    if not manifest:
        print("Falha ao carregar manifest. Encerrando.")
        return

    print(f"manifest: {manifest}\n")

    SEGMENT_DURATION_S = manifest.get("segment_duration_s", 2.0)

    # ── Seleciona a política ABR ─────────────────────────────────────────────
    if policy == 2:
        try:
            from abr_v2 import BufferBasedABR
            abr = BufferBasedABR(manifest)
            label_policy = "POLÍTICA 2 – BUFFER-BASED"
        except ImportError:
            print("[AVISO] abr_v2.py não encontrado – usando Política 1 como fallback.")
            abr = RateBasedABR(manifest)
            label_policy = "POLÍTICA 1 – RATE-BASED (fallback)"
    else:
        abr = RateBasedABR(manifest)
        label_policy = "POLÍTICA 1 – RATE-BASED BASELINE"

    # ── Objetos de suporte ───────────────────────────────────────────────────
    buffer   = BufferManager()
    csv_file = f"streaming_metrics_p{policy}.csv"
    logger   = MetricsLogger(csv_file)

    jitter_ewma_ms = 0.0

    print("\n" + "=" * 55)
    print(f"  INICIANDO STREAMING  |  {label_policy}")
    print(f"  Servidor inicial    : {client.current_server_id} ({client.current_server_url})")
    print("=" * 55 + "\n")

    for num_segmento in range(1, total_segments + 1):
        print(f"\n{'─'*50}")
        print(f"  Segmento {num_segmento}/{total_segments}  |  "
              f"Servidor: {client.current_server_id}  |  "
              f"Buffer: {buffer.get_current_level():.2f}s")
        print(f"{'─'*50}")

        # ── Pausa se buffer estiver cheio ────────────────────────────────────
        if buffer.should_pause():
            buffer.wait_until_resumable(SEGMENT_DURATION_S)

        # ── Decisão ABR ──────────────────────────────────────────────────────
        try:
            qualidade_escolhida = abr.get_next_quality(
                buffer_level_s=buffer.get_current_level()
            )
        except TypeError:
            qualidade_escolhida = abr.get_next_quality()

        rep_escolhida   = next(
            r for r in manifest["representations"]
            if r["quality"] == qualidade_escolhida
        )
        bitrate_nominal = rep_escolhida["bitrate_kbps"]
        url_path        = rep_escolhida["url_path"]
        expected_bytes  = rep_escolhida.get("segment_bytes", 0)

        # ── Download do segmento ─────────────────────────────────────────────
        tamanho, download_time_s, throughput_kbps, jitter_network_ms, houve_failover = \
            client.download_segment(url_path, expected_bytes=expected_bytes)

        # ── Atualiza EWMA do jitter entre segmentos ──────────────────────────
        jitter_ewma_ms = atualizar_ewma(jitter_ewma_ms, jitter_network_ms)

        # ── Atualiza histórico do ABR ────────────────────────────────────────
        if throughput_kbps > 0:
            abr.record_throughput(throughput_kbps)

        # ── Atualiza o buffer ────────────────────────────────────────────────
        buffer_can_play, rebuffer_event, stall_duration_s = \
            buffer.update_buffer(download_time_s, SEGMENT_DURATION_S)

        if houve_failover:
            print(f"[Main] Failover no segmento {num_segmento}. "
                  f"buffer_can_play={buffer_can_play} "
                  f"({'buffer suficiente ✅' if buffer_can_play else 'buffer insuficiente ⚠️'})")

        # ── Grava no CSV ─────────────────────────────────────────────────────
        dados_segmento = {
            "segment"           : num_segmento,
            "server_id"         : client.current_server_id,
            "quality"           : qualidade_escolhida,
            "bitrate_kbps"      : bitrate_nominal,
            "throughput_kbps"   : throughput_kbps,
            "download_time_s"   : download_time_s,
            "jitter_network_ms" : jitter_network_ms,
            "jitter_ewma_ms"    : jitter_ewma_ms,
            "buffer_level_s"    : buffer.get_current_level(),
            "buffer_can_play"   : buffer_can_play,
            "rebuffer_event"    : rebuffer_event,
            "stall_duration_s"  : stall_duration_s,
            "failover_total"    : client.failover_total,
        }
        logger.log_segment(dados_segmento)

        time.sleep(0.3)

    # ── Resumo da sessão ──────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  STREAMING CONCLUÍDO")
    print(f"  Política        : {label_policy}")
    print(f"  Arquivo CSV     : {csv_file}")
    print(f"  Failovers total : {client.failover_total}")
    print(f"  {buffer.summary()}")
    print("=" * 55)

    return csv_file


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente de Streaming Adaptativo")
    parser.add_argument("--policy", type=int, default=1, choices=[1, 2],
                        help="Política ABR: 1=Rate-Based (baseline), 2=Buffer-Based")
    parser.add_argument("--segments", type=int, default=20,
                        help="Número de segmentos a baixar")
    args = parser.parse_args()

    csv_file = run_client(policy=args.policy, total_segments=args.segments)

    if csv_file:
        print("\nGerando gráficos…")
        plot.generate_throughput_quality_chart(csv_file)