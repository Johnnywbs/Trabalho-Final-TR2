import csv
import matplotlib.pyplot as plt

def generate_chart(csv_filename):
    segments, throughput_kbps, quality_kbps, buffer_s, quality_names = [], [], [], [], []

    try:
        with open(csv_filename, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                segments.append(int(row["segment"]))
                throughput_kbps.append(float(row["throughput_kbps"]))
                quality_kbps.append(float(row["bitrate_kbps"]))
                buffer_s.append(float(row["buffer_level_s"]))
                quality_names.append(row["quality"]) # Capturando o nome da resolução!
    except FileNotFoundError:
        print(f"Erro: Arquivo '{csv_filename}' não encontrado.")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # Gráfico 1: Rede vs Bitrate
    ax1.plot(segments, throughput_kbps, label="Rede (Throughput)", color="lightseagreen", linestyle=":", marker=".", alpha=0.8)
    ax1.step(segments, quality_kbps, label="Decisão P2 (Bitrate)", color="teal", where='mid', linewidth=3)
    
    # Adicionando os textos das qualidades (240p, 720p, etc) flutuando em cima da linha
    for i, txt in enumerate(quality_names):
        ax1.annotate(txt, (segments[i], quality_kbps[i]), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=9, color='darkslategray', fontweight='bold')

    ax1.set_ylabel("Largura de Banda (kbps)")
    ax1.set_title("Política 2 (Preditiva): Análise Isolada", fontweight='bold')
    ax1.grid(True, linestyle=":", alpha=0.7)
    ax1.legend(loc="upper left")

    # Gráfico 2: Evolução do Buffer
    ax2.plot(segments, buffer_s, label="Nível do Buffer", color="teal", linestyle="-", marker="s")
    ax2.axhline(y=3.5, color='orange', linestyle='--', alpha=0.5, label="Limite Superior (Sobe Qualidade)")
    ax2.axhline(y=2.0, color='red', linestyle='--', alpha=0.5, label="Limite Inferior (Desce Qualidade)")
    
    ax2.set_xlabel("Número do Segmento")
    ax2.set_ylabel("Segundos em Buffer (s)")
    ax2.grid(True, linestyle=":", alpha=0.7)
    ax2.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig("chart_policy2_only.png", dpi=300)
    print("Gráfico 'chart_policy2_only.png' gerado com sucesso!")
    plt.show()

if __name__ == "__main__":
    generate_chart("streaming_metrics_p2.csv")