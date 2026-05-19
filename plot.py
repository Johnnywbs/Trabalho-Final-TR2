import csv
import matplotlib.pyplot as plt

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

    plt.savefig("baseline_chart.png", dpi=300)
    print("Chart saved as 'baseline_chart.png'!")
    plt.show()


if __name__ == "__main__":
    generate_throughput_quality_chart("streaming_metrics.csv")
