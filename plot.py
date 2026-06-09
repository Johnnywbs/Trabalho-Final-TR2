import csv
import os
import matplotlib.pyplot as plt

CHARTS_DIR = "charts"

def generate_throughput_quality_chart(csv_filename):
    segments = []
    throughput_kbps = []
    quality_kbps = []
    quality_names = []

    try:
        with open(csv_filename, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                segments.append(int(row["segment"]))
                throughput_kbps.append(float(row["throughput_kbps"]))
                quality_kbps.append(float(row["bitrate_kbps"]))
                quality_names.append(row["quality"])
    except FileNotFoundError:
        print(f"Error: File '{csv_filename}' not found.")
        return

    plt.figure(figsize=(10, 6))

    plt.plot(segments, throughput_kbps, label="Network Throughput (kbps)",
             color="blue", linestyle="--", marker="o", linewidth=2)

    plt.step(segments, quality_kbps, label="Selected Quality (Bitrate)",
             color="darkorange", linewidth=3, where='mid')

    plt.title("Baseline ABR Behavior (Rate-Based)", fontsize=14, fontweight='bold')
    plt.xlabel("Segment Number", fontsize=12)
    plt.ylabel("Bandwidth (kbps)", fontsize=12)

    for i, label in enumerate(quality_names):
        plt.annotate(label, (segments[i], quality_kbps[i]),
                     textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9)

    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(loc="upper left")
    plt.tight_layout()

    os.makedirs(CHARTS_DIR, exist_ok=True)
    out = os.path.join(CHARTS_DIR, "baseline_chart.png")
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"Chart saved as '{out}'!")


if __name__ == "__main__":
    generate_throughput_quality_chart("streaming_metrics.csv")


# ---------------------------------------------------------------------------
# Funções de comparação P1 vs P2
# ---------------------------------------------------------------------------

def _load_csv_columns(path, *cols):
    """Retorna dict {col: [valores]} para as colunas pedidas."""
    result = {c: [] for c in cols}
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for c in cols:
                    result[c].append(row[c])
    except FileNotFoundError:
        print(f"[plot] Arquivo não encontrado: {path}")
    return result


def _failover_segs(path):
    """Retorna lista de números de segmentos onde houve failover."""
    segs = []
    prev_ft = 0
    try:
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ft = int(row["failover_total"])
                if ft > prev_ft:
                    segs.append(int(row["segment"]))
                prev_ft = ft
    except FileNotFoundError:
        pass
    return segs


def _rebuffer_segs(data_dict):
    """Retorna lista de segmentos com rebuffer_event=1."""
    return [
        int(s) for s, v in zip(data_dict["segment"], data_dict["rebuffer_event"])
        if v == "1"
    ]


QUALITY_ORDER = {"240p": 0, "360p": 1, "480p": 2, "720p": 3, "1080p": 4}
ALL_QUALITIES = ["240p", "360p", "480p", "720p", "1080p"]


def generate_comparison_chart(csv_p1, csv_p2, output="comparison_chart.png"):
    """Gráfico sobreposto: throughput e qualidade de P1 vs P2."""
    cols = ["segment", "throughput_kbps", "bitrate_kbps", "quality", "rebuffer_event"]
    d1 = _load_csv_columns(csv_p1, *cols)
    d2 = _load_csv_columns(csv_p2, *cols)

    if not d1["segment"] or not d2["segment"]:
        print("[plot] Dados insuficientes para comparison_chart.")
        return

    segs1 = [int(x) for x in d1["segment"]]
    segs2 = [int(x) for x in d2["segment"]]
    tput1 = [float(x) for x in d1["throughput_kbps"]]
    tput2 = [float(x) for x in d2["throughput_kbps"]]
    br1   = [float(x) for x in d1["bitrate_kbps"]]
    br2   = [float(x) for x in d2["bitrate_kbps"]]

    rb1 = _rebuffer_segs(d1)
    rb2 = _rebuffer_segs(d2)
    fo2 = _failover_segs(csv_p2)

    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    ax1.plot(segs1, tput1, color="steelblue", linestyle="--",
             linewidth=1.5, label="Throughput P1")
    ax1.plot(segs2, tput2, color="seagreen", linestyle="--",
             linewidth=1.5, label="Throughput P2")
    for s in rb1 + rb2:
        ax1.axvline(s, color="red", alpha=0.4, linewidth=1)
    for s in fo2:
        ax1.axvline(s, color="orange", linestyle=":", linewidth=1.5)
    ax1.set_ylabel("Throughput (kbps)", fontsize=11)
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_title("Comparação P1 (Rate-Based) vs P2 (Buffer-Based)", fontsize=13, fontweight="bold")

    ax2.step(segs1, br1, color="darkorange", linewidth=2.5,
             where="mid", label="Qualidade P1 (bitrate)")
    ax2.step(segs2, br2, color="mediumpurple", linewidth=2.5,
             where="mid", label="Qualidade P2 (bitrate)")
    for s in rb1:
        ax2.axvline(s, color="red", alpha=0.4, linewidth=1, label="Rebuffer P1" if s == rb1[0] else "")
    for s in rb2:
        ax2.axvline(s, color="tomato", alpha=0.4, linewidth=1)
    for s in fo2:
        ax2.axvline(s, color="orange", linestyle=":", linewidth=1.5,
                    label=f"Failover (seg {s})")
    ax2.set_xlabel("Segmento", fontsize=11)
    ax2.set_ylabel("Bitrate nominal (kbps)", fontsize=11)
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_buffer_chart(csv_p1, csv_p2, output="buffer_chart.png"):
    """Nível do buffer P1 vs P2 com marcadores de rebuffer e limiares."""
    cols = ["segment", "buffer_level_s", "rebuffer_event"]
    d1 = _load_csv_columns(csv_p1, *cols)
    d2 = _load_csv_columns(csv_p2, *cols)

    if not d1["segment"] or not d2["segment"]:
        print("[plot] Dados insuficientes para buffer_chart.")
        return

    segs1  = [int(x) for x in d1["segment"]]
    segs2  = [int(x) for x in d2["segment"]]
    buf1   = [float(x) for x in d1["buffer_level_s"]]
    buf2   = [float(x) for x in d2["buffer_level_s"]]
    rb1    = _rebuffer_segs(d1)
    rb2    = _rebuffer_segs(d2)
    fo2    = _failover_segs(csv_p2)

    _, ax = plt.subplots(figsize=(11, 5))

    ax.plot(segs1, buf1, color="steelblue", linewidth=2, marker="o",
            markersize=4, label="Buffer P1 (Rate-Based)")
    ax.plot(segs2, buf2, color="seagreen", linewidth=2, marker="s",
            markersize=4, label="Buffer P2 (Buffer-Based)")

    for s in rb1:
        idx = segs1.index(s)
        ax.annotate("▼", (s, buf1[idx]), color="red", fontsize=12,
                    ha="center", va="top")
    for s in rb2:
        idx = segs2.index(s)
        ax.annotate("▼", (s, buf2[idx]), color="tomato", fontsize=12,
                    ha="center", va="top")
    for s in fo2:
        ax.axvline(s, color="orange", linestyle=":", linewidth=1.5,
                   label=f"Failover (seg {s})")

    ax.axhline(4,  color="red",    linestyle="--", alpha=0.5, linewidth=1.2,
               label="Limiar emergência (4s)")
    ax.axhline(8,  color="orange", linestyle="--", alpha=0.5, linewidth=1.2,
               label="Limiar baixo (8s)")
    ax.axhline(15, color="green",  linestyle="--", alpha=0.5, linewidth=1.2,
               label="Limiar alto (15s)")

    ax.set_title("Nível do Buffer ao Longo do Tempo", fontsize=13, fontweight="bold")
    ax.set_xlabel("Segmento", fontsize=11)
    ax.set_ylabel("Buffer (s)", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_jitter_chart(csv_p1, csv_p2, output="jitter_chart.png"):
    """EWMA do jitter P1 vs P2 sobrepostos."""
    cols = ["segment", "jitter_ewma_ms"]
    d1 = _load_csv_columns(csv_p1, *cols)
    d2 = _load_csv_columns(csv_p2, *cols)

    if not d1["segment"] or not d2["segment"]:
        print("[plot] Dados insuficientes para jitter_chart.")
        return

    segs1 = [int(x) for x in d1["segment"]]
    segs2 = [int(x) for x in d2["segment"]]
    j1    = [float(x) for x in d1["jitter_ewma_ms"]]
    j2    = [float(x) for x in d2["jitter_ewma_ms"]]

    avg1 = round(sum(j1) / len(j1), 2) if j1 else 0
    avg2 = round(sum(j2) / len(j2), 2) if j2 else 0

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(segs1, j1, color="steelblue", linewidth=2, marker="o", markersize=4,
            label=f"Jitter EWMA P1  (média {avg1} ms)")
    ax.plot(segs2, j2, color="seagreen", linewidth=2, marker="s", markersize=4,
            label=f"Jitter EWMA P2  (média {avg2} ms)")

    ax.set_title("Variação de Atraso (Jitter EWMA) — P1 vs P2", fontsize=13, fontweight="bold")
    ax.set_xlabel("Segmento", fontsize=11)
    ax.set_ylabel("Jitter EWMA (ms)", fontsize=11)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_quality_distribution_chart(csv_p1, csv_p2, output="quality_dist_chart.png"):
    """Barras agrupadas: % de tempo em cada nível de qualidade P1 vs P2."""
    def get_dist(path):
        counts = {q: 0 for q in ALL_QUALITIES}
        total  = 0
        try:
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    q = row["quality"]
                    if q in counts:
                        counts[q] += 1
                    total += 1
        except FileNotFoundError:
            pass
        return {q: round(counts[q] / total * 100, 1) if total else 0 for q in ALL_QUALITIES}

    dist1 = get_dist(csv_p1)
    dist2 = get_dist(csv_p2)

    import numpy as np
    x     = np.arange(len(ALL_QUALITIES))
    width = 0.35

    _, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x - width/2, [dist1[q] for q in ALL_QUALITIES], width,
                   label="P1 (Rate-Based)", color="steelblue", alpha=0.85)
    bars2 = ax.bar(x + width/2, [dist2[q] for q in ALL_QUALITIES], width,
                   label="P2 (Buffer-Based)", color="seagreen", alpha=0.85)

    ax.bar_label(bars1, fmt="%.1f%%", padding=2, fontsize=9)
    ax.bar_label(bars2, fmt="%.1f%%", padding=2, fontsize=9)

    ax.set_title("Distribuição de Qualidade Selecionada — P1 vs P2", fontsize=13, fontweight="bold")
    ax.set_xlabel("Nível de Qualidade", fontsize=11)
    ax.set_ylabel("% do tempo", fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(ALL_QUALITIES)
    ax.set_ylim(0, 110)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_all_charts(csv_p1="streaming_metrics_p1.csv",
                        csv_p2="streaming_metrics_p2.csv"):
    os.makedirs(CHARTS_DIR, exist_ok=True)
    generate_comparison_chart(csv_p1, csv_p2,
                              output=os.path.join(CHARTS_DIR, "comparison_chart.png"))
    generate_buffer_chart(csv_p1, csv_p2,
                          output=os.path.join(CHARTS_DIR, "buffer_chart.png"))
    generate_jitter_chart(csv_p1, csv_p2,
                          output=os.path.join(CHARTS_DIR, "jitter_chart.png"))
    generate_quality_distribution_chart(csv_p1, csv_p2,
                                        output=os.path.join(CHARTS_DIR, "quality_dist_chart.png"))
