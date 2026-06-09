"""
analysis.py  –  Análise de deficiências e comparação de políticas ABR

Uso:
    python analysis.py [--p1 arquivo.csv] [--p2 arquivo.csv]

Padrão: streaming_metrics_p1.csv  vs  streaming_metrics_p2.csv
"""

import argparse
import csv
import os


# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------

def load_csv(path):
    if not os.path.exists(path):
        print(f"[analysis] Arquivo não encontrado: {path}")
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "segment"          : int(row["segment"]),
                "timestamp"        : row["timestamp"],
                "server_id"        : row["server_id"],
                "quality"          : row["quality"],
                "bitrate_kbps"     : float(row["bitrate_kbps"]),
                "throughput_kbps"  : float(row["throughput_kbps"]),
                "download_time_s"  : float(row["download_time_s"]),
                "jitter_network_ms": float(row["jitter_network_ms"]),
                "jitter_ewma_ms"   : float(row["jitter_ewma_ms"]),
                "buffer_level_s"   : float(row["buffer_level_s"]),
                "buffer_can_play"  : int(row["buffer_can_play"]),
                "rebuffer_event"   : int(row["rebuffer_event"]),
                "stall_duration_s" : float(row["stall_duration_s"]),
                "failover_total"   : int(row["failover_total"]),
            })
    return rows


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def oscillation_count(rows):
    """Número de trocas consecutivas de qualidade."""
    changes = 0
    for i in range(1, len(rows)):
        if rows[i]["quality"] != rows[i - 1]["quality"]:
            changes += 1
    return changes


def rebuffer_stats(rows):
    """{'count': int, 'rate_pct': float, 'total_stall_s': float}"""
    if not rows:
        return {"count": 0, "rate_pct": 0.0, "total_stall_s": 0.0}
    count       = sum(r["rebuffer_event"] for r in rows)
    total_stall = sum(r["stall_duration_s"] for r in rows)
    rate_pct    = count / len(rows) * 100
    return {"count": count, "rate_pct": rate_pct, "total_stall_s": total_stall}


def adaptation_speed(rows):
    """
    Número de segmentos até a qualidade se estabilizar
    (não mudar por 3 consecutivos).
    """
    stable_run = 0
    for i in range(1, len(rows)):
        if rows[i]["quality"] == rows[i - 1]["quality"]:
            stable_run += 1
            if stable_run >= 3:
                return i - 2   # segmento onde a estabilidade começou
        else:
            stable_run = 0
    return len(rows)


def quality_distribution(rows):
    """{'240p': 5.0, '480p': 95.0, ...} em %"""
    if not rows:
        return {}
    counts = {}
    for r in rows:
        counts[r["quality"]] = counts.get(r["quality"], 0) + 1
    total = len(rows)
    return {q: round(c / total * 100, 1) for q, c in sorted(counts.items())}


def avg_buffer_level(rows):
    if not rows:
        return 0.0
    return round(sum(r["buffer_level_s"] for r in rows) / len(rows), 2)


def avg_throughput(rows):
    if not rows:
        return 0.0
    return round(sum(r["throughput_kbps"] for r in rows) / len(rows), 1)


def failover_analysis(rows):
    """
    Para cada segmento onde failover_total muda, retorna:
    {'segment', 'old_server', 'new_server', 'buffer_before',
     'buffer_can_play', 'quality_after'}
    """
    events = []
    for i in range(1, len(rows)):
        if rows[i]["failover_total"] > rows[i - 1]["failover_total"]:
            events.append({
                "segment"        : rows[i]["segment"],
                "old_server"     : rows[i - 1]["server_id"],
                "new_server"     : rows[i]["server_id"],
                "buffer_before"  : rows[i - 1]["buffer_level_s"],
                "buffer_can_play": rows[i]["buffer_can_play"],
                "quality_after"  : rows[i]["quality"],
                "throughput_before": rows[i - 1]["throughput_kbps"],
                "throughput_after" : rows[i]["throughput_kbps"],
            })
    return events


# ---------------------------------------------------------------------------
# Saída formatada
# ---------------------------------------------------------------------------

def _dist_str(dist):
    return "  ".join(f"{k}={v}%" for k, v in dist.items())


def print_policy_analysis(label, rows):
    if not rows:
        print(f"  (sem dados para {label})")
        return

    osc  = oscillation_count(rows)
    rb   = rebuffer_stats(rows)
    spd  = adaptation_speed(rows)
    dist = quality_distribution(rows)
    abuf = avg_buffer_level(rows)
    atpt = avg_throughput(rows)

    print(f"\n{'='*48}")
    print(f"  ANÁLISE DE DEFICIÊNCIAS — {label}")
    print(f"{'='*48}")
    print(f"  Segmentos analisados    : {len(rows)}")
    print(f"  Oscilações de qualidade : {osc}")
    print(f"  Eventos de rebuffer     : {rb['count']}  ({rb['rate_pct']:.1f}%)")
    print(f"  Stall total             : {rb['total_stall_s']:.2f}s")
    print(f"  Adaptação (segmentos)   : {spd}")
    print(f"  Distribuição            : {_dist_str(dist)}")
    print(f"  Buffer médio            : {abuf:.2f}s")
    print(f"  Throughput médio        : {atpt:.1f} kbps")


def print_failover_analysis(label, rows):
    events = failover_analysis(rows)
    if not events:
        return
    print(f"\n{'='*48}")
    print(f"  ANÁLISE DE FAILOVER — {label}")
    print(f"{'='*48}")
    for ev in events:
        absorveu = "buffer suficiente ✅" if ev["buffer_can_play"] else "rebuffer ⚠️"
        print(
            f"  Seg {ev['segment']:>3} | {ev['old_server']} → {ev['new_server']} | "
            f"buffer antes={ev['buffer_before']:.1f}s | {absorveu} | "
            f"qualidade pós={ev['quality_after']}"
        )
        print(
            f"           throughput antes={ev['throughput_before']:.0f} kbps → "
            f"depois={ev['throughput_after']:.0f} kbps"
        )


def print_comparison_table(rows_p1, rows_p2):
    ALL_QUALITIES = ["240p", "360p", "480p", "720p", "1080p"]

    def fmt(v, fmt_str="{:.1f}"):
        return fmt_str.format(v) if v is not None else "N/A"

    def safe_metric(rows, fn):
        return fn(rows) if rows else None

    osc1  = safe_metric(rows_p1, oscillation_count)
    osc2  = safe_metric(rows_p2, oscillation_count)
    rb1   = safe_metric(rows_p1, rebuffer_stats) or {}
    rb2   = safe_metric(rows_p2, rebuffer_stats) or {}
    spd1  = safe_metric(rows_p1, adaptation_speed)
    spd2  = safe_metric(rows_p2, adaptation_speed)
    buf1  = safe_metric(rows_p1, avg_buffer_level)
    buf2  = safe_metric(rows_p2, avg_buffer_level)
    tpt1  = safe_metric(rows_p1, avg_throughput)
    tpt2  = safe_metric(rows_p2, avg_throughput)
    dist1 = safe_metric(rows_p1, quality_distribution) or {}
    dist2 = safe_metric(rows_p2, quality_distribution) or {}

    W = 10
    sep = f"  {'-'*25}|{'-'*W}|{'-'*W}"

    print(f"\n{'='*48}")
    print(f"  COMPARAÇÃO P1 vs P2")
    print(f"{'='*48}")
    print(f"  {'Métrica':<25}| {'P1':^{W-1}}| {'P2':^{W-1}}")
    print(sep)
    print(f"  {'Oscilações':<25}| {str(osc1):^{W-1}}| {str(osc2):^{W-1}}")
    print(f"  {'Rebuffer eventos':<25}| {str(rb1.get('count','N/A')):^{W-1}}| {str(rb2.get('count','N/A')):^{W-1}}")
    print(f"  {'Taxa rebuffer (%)':<25}| {fmt(rb1.get('rate_pct')):^{W-1}}| {fmt(rb2.get('rate_pct')):^{W-1}}")
    print(f"  {'Stall total (s)':<25}| {fmt(rb1.get('total_stall_s'), '{:.2f}'):^{W-1}}| {fmt(rb2.get('total_stall_s'), '{:.2f}'):^{W-1}}")
    print(f"  {'Adaptação (segs)':<25}| {str(spd1):^{W-1}}| {str(spd2):^{W-1}}")
    print(f"  {'Buffer médio (s)':<25}| {fmt(buf1, '{:.2f}'):^{W-1}}| {fmt(buf2, '{:.2f}'):^{W-1}}")
    print(f"  {'Throughput médio (kbps)':<25}| {fmt(tpt1, '{:.1f}'):^{W-1}}| {fmt(tpt2, '{:.1f}'):^{W-1}}")
    print(sep)
    print(f"  {'Distribuição de qualidade':}")
    for q in ALL_QUALITIES:
        v1 = dist1.get(q, 0.0)
        v2 = dist2.get(q, 0.0)
        print(f"    {q:<6}{'%':>3}           | {fmt(v1, '{:.1f}'):^{W-1}}| {fmt(v2, '{:.1f}'):^{W-1}}")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Análise de políticas ABR")
    parser.add_argument("--p1", default="streaming_metrics_p1.csv")
    parser.add_argument("--p2", default="streaming_metrics_p2.csv")
    parser.add_argument("--no-charts", action="store_true",
                        help="Não gerar gráficos (útil se matplotlib não estiver disponível)")
    args = parser.parse_args()

    rows_p1 = load_csv(args.p1)
    rows_p2 = load_csv(args.p2)

    print_policy_analysis("POLÍTICA 1 (RATE-BASED BASELINE)", rows_p1)
    print_policy_analysis("POLÍTICA 2 (BUFFER-BASED)", rows_p2)
    print_failover_analysis("POLÍTICA 2", rows_p2)
    print_comparison_table(rows_p1, rows_p2)

    if not args.no_charts:
        try:
            import plot
            print("\nGerando gráficos comparativos…")
            plot.generate_all_charts(args.p1, args.p2)
            print("Gráficos salvos: comparison_chart.png, buffer_chart.png, "
                  "jitter_chart.png, quality_dist_chart.png")
        except ImportError as exc:
            print(f"\n[analysis] matplotlib não disponível — gráficos ignorados ({exc})")


if __name__ == "__main__":
    main()
