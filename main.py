"""
main.py — Orquestrador do cliente de streaming adaptativo (ABR)

Uso:
    python main.py [--politica {1,2,3}] [--segmentos N]

    --politica 1   Rate-Based baseline (padrão)
    --politica 2   Buffer-Based ABR
    --politica 3   Estatístico Híbrido (mean−k·std + penalidade de jitter)
    --segmentos N  número de segmentos a baixar (padrão: 20)
"""

import argparse

from client         import StreamingClient
from abr            import RateBasedABR
from buffer_manager import BufferManager
from metrics        import MetricsLogger
import plot

# Alpha da EWMA de jitter entre segmentos — usado para log no CSV.
ALPHA_EWMA_JITTER = 0.2


# =============================================================================
# Funções auxiliares
# =============================================================================

def atualizar_ewma(valor_anterior: float, novo_valor: float) -> float:
    """Calcula um passo da Média Móvel Exponencial Ponderada (EWMA)."""
    return ALPHA_EWMA_JITTER * novo_valor + (1 - ALPHA_EWMA_JITTER) * valor_anterior


def selecionar_politica(policy: int, manifest: dict):
    """Instancia e retorna o objeto ABR correspondente à política escolhida."""
    if policy == 2:
        try:
            from abr_v2 import BufferBasedABR
            return BufferBasedABR(manifest), "POLÍTICA 2 — BUFFER-BASED"
        except ImportError:
            print("[AVISO] abr_v2.py não encontrado — usando Política 1 como fallback.")
    elif policy == 3:
        try:
            from abr_v3 import HybridStatisticalABR
            return HybridStatisticalABR(manifest), "POLÍTICA 3 — ESTATÍSTICO HÍBRIDO"
        except ImportError:
            print("[AVISO] abr_v3.py não encontrado — usando Política 1 como fallback.")

    return RateBasedABR(manifest), "POLÍTICA 1 — RATE-BASED BASELINE"


# =============================================================================
# Laço principal de streaming
# =============================================================================

def executar_cliente(policy: int = 1, total_segmentos: int = 20):

    # --- Carrega o manifest e descobre os servidores disponíveis ---
    cliente  = StreamingClient()
    manifest = cliente.fetch_manifest()

    if not manifest:
        print("[ERRO] Falha ao carregar o manifest. Encerrando.")
        return None

    duracao_segmento_s = manifest.get("segment_duration_s", 2.0)

    # --- Seleciona a política ABR ---
    abr, label_politica = selecionar_politica(policy, manifest)

    # --- Inicializa os componentes de suporte ---
    buffer    = BufferManager()
    csv_file  = f"streaming_metrics_p{policy}.csv"
    logger    = MetricsLogger(csv_file)
    jitter_ewma_ms = 0.0

    # --- Cabeçalho da sessão ---
    print("\n" + "=" * 58)
    print(f"  INICIANDO STREAMING  |  {label_politica}")
    print(f"  Servidor inicial     : {cliente.current_server_id}"
          f" ({cliente.current_server_url})")
    print(f"  Segmentos            : {total_segmentos}"
          f"  |  Duração/seg: {duracao_segmento_s}s")
    print("=" * 58 + "\n")

    # --- Loop de download de segmentos ---
    for num_seg in range(1, total_segmentos + 1):

        print(f"\n{'─'*52}")
        print(f"  Segmento {num_seg}/{total_segmentos}"
              f"  |  Servidor: {cliente.current_server_id}"
              f"  |  Buffer: {buffer.get_current_level():.2f}s")
        print(f"{'─'*52}")

        # Pausa o download se o buffer já estiver cheio (evita acumular além do teto).
        if buffer.should_pause():
            buffer.wait_until_resumable(duracao_segmento_s)

        # Consulta o ABR para saber qual qualidade baixar neste segmento.
        qualidade = abr.get_next_quality(buffer_level_s=buffer.get_current_level())

        # Localiza os metadados da representação escolhida no manifest.
        rep = next(r for r in manifest["representations"] if r["quality"] == qualidade)
        bitrate_nominal = rep["bitrate_kbps"]
        url_path        = rep["url_path"]
        bytes_esperados = rep.get("segment_bytes", 0)

        # Baixa o segmento e mede as métricas de rede.
        tamanho, tempo_download_s, vazao_kbps, jitter_ms, houve_failover = \
            cliente.download_segment(url_path, expected_bytes=bytes_esperados)

        # Atualiza a EWMA de jitter (usada apenas para log no CSV).
        jitter_ewma_ms = atualizar_ewma(jitter_ewma_ms, jitter_ms)

        # Informa a nova medição ao ABR para atualizar o histórico.
        if vazao_kbps > 0:
            abr.record_throughput(vazao_kbps, jitter_ms)

        # Atualiza a simulação do buffer (consumo + reabastecimento + detecção de stall).
        buffer_ok, evento_rebuffer, duracao_stall_s = \
            buffer.update_buffer(tempo_download_s, duracao_segmento_s)

        # Informa o failover no terminal quando ocorre.
        if houve_failover:
            status = "buffer suficiente" if buffer_ok else "rebuffering detectado"
            print(f"[FAILOVER] Segmento {num_seg}: migrado para {cliente.current_server_id}"
                  f" — {status}")

        # Grava a linha do CSV com todas as métricas deste segmento.
        logger.log_segment({
            "segment"           : num_seg,
            "server_id"         : cliente.current_server_id,
            "quality"           : qualidade,
            "bitrate_kbps"      : bitrate_nominal,
            "throughput_kbps"   : vazao_kbps,
            "download_time_s"   : tempo_download_s,
            "jitter_network_ms" : jitter_ms,
            "jitter_ewma_ms"    : jitter_ewma_ms,
            "buffer_level_s"    : buffer.get_current_level(),
            "buffer_can_play"   : buffer_ok,
            "rebuffer_event"    : evento_rebuffer,
            "stall_duration_s"  : duracao_stall_s,
            "failover_total"    : cliente.failover_total,
        })

        # Simula o ritmo de playback: só pacea após o buffer atingir o nível-alvo.
        buffer.pace_playback(tempo_download_s, duracao_segmento_s)

    # --- Resumo final da sessão ---
    print("\n" + "=" * 58)
    print("  STREAMING CONCLUÍDO")
    print(f"  Política     : {label_politica}")
    print(f"  Arquivo CSV  : {csv_file}")
    print(f"  Failovers    : {cliente.failover_total}")
    print(f"  {buffer.summary()}")
    print("=" * 58)

    return csv_file


# =============================================================================
# Ponto de entrada
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente de Streaming Adaptativo ABR")
    parser.add_argument(
        "--policy", "--politica",
        type=int, default=1, choices=[1, 2, 3],
        dest="policy",
        help="Política ABR: 1=Rate-Based, 2=Buffer-Based, 3=Estatístico Híbrido"
    )
    parser.add_argument(
        "--segments", "--segmentos",
        type=int, default=20,
        dest="segments",
        help="Número de segmentos a baixar (padrão: 20)"
    )
    args = parser.parse_args()

    csv_gerado = executar_cliente(policy=args.policy, total_segmentos=args.segments)

    if csv_gerado:
        print("\nGerando gráfico da sessão…")
        plot.generate_throughput_quality_chart(csv_gerado)
