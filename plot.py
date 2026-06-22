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

POLICY_COLORS   = ["steelblue", "seagreen", "darkorange", "mediumpurple", "crimson"]
POLICY_MARKERS  = ["o", "s", "^", "D", "v"]
FAILOVER_COLORS = ["red", "purple", "brown", "teal"]


def generate_comparison_chart(csv_paths: dict, output="comparison_chart.png"):
    """Gráfico sobreposto: throughput e qualidade de N políticas."""
    cols = ["segment", "throughput_kbps", "bitrate_kbps", "quality", "rebuffer_event"]
    data = {label: _load_csv_columns(path, *cols) for label, path in csv_paths.items()}
    data = {l: d for l, d in data.items() if d["segment"]}

    if not data:
        print("[plot] Dados insuficientes para comparison_chart.")
        return

    # Mapeamento resolução → índice numérico para o eixo Y
    quality_to_idx = {q: i for i, q in enumerate(ALL_QUALITIES)}

    _, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for i, (label, d) in enumerate(data.items()):
        color = POLICY_COLORS[i % len(POLICY_COLORS)]
        segs  = [int(x) for x in d["segment"]]
        tput  = [float(x) for x in d["throughput_kbps"]]
        qual  = [quality_to_idx.get(q, 0) for q in d["quality"]]
        rb    = _rebuffer_segs(d)
        fo    = _failover_segs(csv_paths[label])

        ax1.plot(segs, tput, color=color, linestyle="--", linewidth=1.5,
                 label=f"Throughput {label}")
        for s in rb:
            ax1.axvline(s, color="red", alpha=0.3, linewidth=1)
        for s in fo:
            ax1.axvline(s, color="orange", linestyle=":", linewidth=1.5)

        ax2.step(segs, qual, color=color, linewidth=2.5, where="mid",
                 label=f"Qualidade {label}")
        for s in rb:
            ax2.axvline(s, color="red", alpha=0.3, linewidth=1)
        for s in fo:
            ax2.axvline(s, color="orange", linestyle=":", linewidth=1.5,
                        label=f"Failover {label} (seg {s})")

    ax1.set_ylabel("Throughput (kbps)", fontsize=11)
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_title(f"Comparação {' vs '.join(data.keys())}", fontsize=13, fontweight="bold")

    ax2.set_xlabel("Segmento", fontsize=11)
    ax2.set_ylabel("Resolução", fontsize=11)
    ax2.set_yticks(range(len(ALL_QUALITIES)))
    ax2.set_yticklabels(ALL_QUALITIES)
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_buffer_chart(csv_paths: dict, output="buffer_chart.png"):
    """Nível do buffer de N políticas com marcadores de rebuffer e limiares."""
    cols = ["segment", "buffer_level_s", "rebuffer_event"]
    data = {label: _load_csv_columns(path, *cols) for label, path in csv_paths.items()}
    data = {l: d for l, d in data.items() if d["segment"]}

    if not data:
        print("[plot] Dados insuficientes para buffer_chart.")
        return

    _, ax = plt.subplots(figsize=(11, 5))

    for i, (label, d) in enumerate(data.items()):
        color  = POLICY_COLORS[i % len(POLICY_COLORS)]
        marker = POLICY_MARKERS[i % len(POLICY_MARKERS)]
        segs   = [int(x) for x in d["segment"]]
        buf    = [float(x) for x in d["buffer_level_s"]]
        rb     = _rebuffer_segs(d)
        fo     = _failover_segs(csv_paths[label])

        ax.plot(segs, buf, color=color, linewidth=2, marker=marker,
                markersize=4, label=f"Buffer {label}")
        for s in rb:
            idx = segs.index(s)
            ax.annotate("▼", (s, buf[idx]), color=color, fontsize=12,
                        ha="center", va="top")
        for j, s in enumerate(fo):
            fo_color = FAILOVER_COLORS[j % len(FAILOVER_COLORS)]
            ax.axvline(s, color=fo_color, linestyle=":", linewidth=1.5,
                       label=f"Failover {label} (seg {s})")

    ax.set_title("Nível do Buffer ao Longo do Tempo", fontsize=13, fontweight="bold")
    ax.set_xlabel("Segmento", fontsize=11)
    ax.set_ylabel("Buffer (s)", fontsize=11)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_jitter_chart(csv_paths: dict, output="jitter_chart.png"):
    """EWMA do jitter de N políticas sobrepostos."""
    cols = ["segment", "jitter_ewma_ms"]
    data = {label: _load_csv_columns(path, *cols) for label, path in csv_paths.items()}
    data = {l: d for l, d in data.items() if d["segment"]}

    if not data:
        print("[plot] Dados insuficientes para jitter_chart.")
        return

    fig, ax = plt.subplots(figsize=(11, 4))
    for i, (label, d) in enumerate(data.items()):
        color  = POLICY_COLORS[i % len(POLICY_COLORS)]
        marker = POLICY_MARKERS[i % len(POLICY_MARKERS)]
        segs   = [int(x) for x in d["segment"]]
        j      = [float(x) for x in d["jitter_ewma_ms"]]
        avg    = round(sum(j) / len(j), 2) if j else 0
        ax.plot(segs, j, color=color, linewidth=2, marker=marker, markersize=4,
                label=f"Jitter EWMA {label}  (média {avg} ms)")

    ax.set_title(f"Variação de Atraso (Jitter EWMA) — {' vs '.join(data.keys())}",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Segmento", fontsize=11)
    ax.set_ylabel("Jitter EWMA (ms)", fontsize=11)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output, dpi=200)
    plt.close()
    print(f"[plot] Salvo: {output}")


def generate_quality_distribution_chart(csv_paths: dict, output="quality_dist_chart.png"):
    """Barras agrupadas: % de tempo em cada nível de qualidade para N políticas."""
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

    dists = {label: get_dist(path) for label, path in csv_paths.items()}

    import numpy as np
    x     = np.arange(len(ALL_QUALITIES))
    n     = len(dists)
    width = 0.8 / n

    _, ax = plt.subplots(figsize=(9, 5))
    for i, (label, dist) in enumerate(dists.items()):
        offset = (i - (n - 1) / 2) * width
        color  = POLICY_COLORS[i % len(POLICY_COLORS)]
        bars   = ax.bar(x + offset, [dist[q] for q in ALL_QUALITIES], width,
                        label=label, color=color, alpha=0.85)
        ax.bar_label(bars, fmt="%.1f%%", padding=2, fontsize=8)

    ax.set_title(f"Distribuição de Qualidade Selecionada — {' vs '.join(dists.keys())}",
                 fontsize=13, fontweight="bold")
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


def generate_all_charts(csv_paths: dict = None):
    """csv_paths: {label: caminho_csv} — ex: {'P1': 'streaming_metrics_p1.csv', ...}"""
    if csv_paths is None:
        csv_paths = {
            "P1": "streaming_metrics_p1.csv",
            "P2": "streaming_metrics_p2.csv",
            "P3": "streaming_metrics_p3.csv",
        }
    csv_paths = {l: p for l, p in csv_paths.items() if os.path.exists(p)}
    os.makedirs(CHARTS_DIR, exist_ok=True)
    generate_comparison_chart(csv_paths,
                              output=os.path.join(CHARTS_DIR, "comparison_chart.png"))
    generate_buffer_chart(csv_paths,
                          output=os.path.join(CHARTS_DIR, "buffer_chart.png"))
    generate_jitter_chart(csv_paths,
                          output=os.path.join(CHARTS_DIR, "jitter_chart.png"))
    generate_quality_distribution_chart(csv_paths,
                                        output=os.path.join(CHARTS_DIR, "quality_dist_chart.png"))
