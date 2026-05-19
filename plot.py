import csv
import matplotlib.pyplot as plt

def gerar_grafico_vazao_qualidade(csv_filename):
    segmentos = []
    vazao_kbps = []
    qualidade_kbps = []
    nomes_qualidade = []

    # 1. Lê os dados do arquivo CSV
    try:
        with open(csv_filename, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                segmentos.append(int(row["segment"]))
                vazao_kbps.append(float(row["vazao_kbps"]))
                qualidade_kbps.append(float(row["bitrate_kbps"]))
                nomes_qualidade.append(row["quality"])
    except FileNotFoundError:
        print(f"Erro: O arquivo {csv_filename} não foi encontrado.")
        return

    # 2. Configura a figura do gráfico
    plt.figure(figsize=(10, 6))

    # 3. Desenha a linha da Vazão da Rede (Azul, tracejada)
    plt.plot(segmentos, vazao_kbps, label="Vazão da Rede (kbps)", 
             color="blue", linestyle="--", marker="o", linewidth=2)

    # 4. Desenha a linha da Qualidade Escolhida (Laranja, linha contínua estilo degrau)
    # Usamos step() porque a qualidade não sobe em rampa, ela muda abruptamente de um segmento para outro
    plt.step(segmentos, qualidade_kbps, label="Qualidade Escolhida (Bitrate)", 
             color="darkorange", linewidth=3, where='mid')

    # 5. Estilização do Gráfico
    plt.title("Comportamento do ABR Baseline (Rate-Based)", fontsize=14, fontweight='bold')
    plt.xlabel("Número do Segmento", fontsize=12)
    plt.ylabel("Banda (kbps)", fontsize=12)
    
    # Adiciona rótulos das resoluções (ex: 240p, 720p) em cima dos pontos laranja
    for i, txt in enumerate(nomes_qualidade):
        plt.annotate(txt, (segmentos[i], qualidade_kbps[i]), 
                     textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(loc="upper left")
    plt.tight_layout()

    # 6. Salva o gráfico como imagem e exibe na tela
    plt.savefig("grafico_baseline.png", dpi=300)
    print("Gráfico salvo como 'grafico_baseline.png'!")
    plt.show()

# Permite testar o gráfico isoladamente se você rodar "python plot.py"
if __name__ == "__main__":
    gerar_grafico_vazao_qualidade("metricas_streaming.csv")