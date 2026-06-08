import csv
import matplotlib.pyplot as plt

def ler_arquivo_metricas(nome_csv):
    segments = []
    bitrates = []
    buffers = []
    throughputs = []  # Adicionado para recuperar a análise de rede
    
    try:
        with open(nome_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                segments.append(int(row["segment"]))
                bitrates.append(float(row["bitrate_kbps"]))
                buffers.append(float(row["buffer_level_s"]))
                throughputs.append(float(row["throughput_kbps"]))
    except FileNotFoundError:
        print(f"Erro: O arquivo {nome_csv} não existe.")
        
    return segments, bitrates, buffers, throughputs

def compare_policies_chart(csv_p1, csv_p2):
    seg_p1, bit_p1, buf_p1, thr_p1 = ler_arquivo_metricas(csv_p1)
    seg_p2, bit_p2, buf_p2, thr_p2 = ler_arquivo_metricas(csv_p2)

    # Cria a janela com dois gráficos empilhados
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    # =========================================================
    # GRÁFICO SUPERIOR: Análise de Rede vs Decisão de Bitrate
    # =========================================================
    
    # Linhas de Rede (Throughput em background)
    ax1.plot(seg_p1, thr_p1, label="Rede durante P1", color="lightcoral", linestyle=":", marker=".", alpha=0.7)
    ax1.plot(seg_p2, thr_p2, label="Rede durante P2", color="lightseagreen", linestyle=":", marker=".", alpha=0.7)
    
    # Degraus de Decisão (Bitrate escolhido)
    ax1.step(seg_p1, bit_p1, label="Decisão P1 (Rate-Based)", color="crimson", where='mid', linewidth=2.5)
    ax1.step(seg_p2, bit_p2, label="Decisão P2 (Buffer-Based)", color="teal", where='mid', linewidth=2.5)
    
    ax1.set_ylabel("Largura de Banda (kbps)")
    ax1.set_title("Comparativo ABR: Comportamento da Rede vs Escolha de Resolução", fontweight='bold')
    ax1.grid(True, linestyle=":")
    
    # Move a legenda para fora para não tampar as linhas da rede
    ax1.legend(loc="upper left", fontsize=9, bbox_to_anchor=(1, 1))

    # =========================================================
    # GRÁFICO INFERIOR: Análise de Sobrevivência (Buffer)
    # =========================================================
    ax2.plot(seg_p1, buf_p1, label="Nível Buffer P1", color="crimson", linestyle="-", marker="o")
    ax2.plot(seg_p2, buf_p2, label="Nível Buffer P2", color="teal", linestyle="-", marker="s")
    
    ax2.set_xlabel("Número do Segmento")
    ax2.set_ylabel("Segundos em Buffer (s)")
    ax2.grid(True, linestyle=":")
    ax2.legend(loc="upper left", fontsize=9, bbox_to_anchor=(1, 1))

    # Ajusta o layout para a legenda caber sem cortar
    plt.tight_layout(rect=[0, 0, 0.85, 1])
    plt.savefig("comparison_chart_network.png", dpi=300)
    print("Gráfico 'comparison_chart_network.png' criado com a análise de rede!")
    plt.show()

if __name__ == "__main__":
    compare_policies_chart("metrics_p1.csv", "metrics_p2.csv")