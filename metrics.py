import csv
from datetime import datetime

class MetricsLogger:
    def __init__(self, filename="metricas_streaming.csv"):
        self.filename = filename
        self._criar_cabecalho()

    def _criar_cabecalho(self):
        """Cria o arquivo e escreve a primeira linha com os nomes das colunas."""
        # Cabeçalhos exatos exigidos na Tabela da página 6 do seu trabalho
        headers = [
            "segment", "timestamp", "server_id", "quality", "bitrate_kbps",
            "vazao_kbps", "download_time_s", "jitter_network_ms",
            "jitter_ewma_ms", "buffer_level_s", "buffer_can_play",
            "rebuffer_event", "stall_duration_s", "failover_total"
        ]
        
        # Abre o arquivo em modo 'w' (write) para sobrescrever/criar um novo arquivo limpo
        with open(self.filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(headers)

    def registrar_segmento(self, dados_segmento):
        """
        Recebe um dicionário com os dados coletados após o download e salva uma nova linha.
        """
        # Extraímos os dados do dicionário, usando valores padrão (0 ou "") se algo faltar
        linha = [
            dados_segmento.get("segment", 0),
            datetime.now().isoformat(), # Gera a data no formato ISO 8601 (ex: 2026-05-18T10:30:00)
            dados_segmento.get("server_id", "A"),
            dados_segmento.get("quality", "Unknown"),
            dados_segmento.get("bitrate_kbps", 0),
            
            # Arredondamos os números decimais para o CSV ficar limpo
            round(dados_segmento.get("vazao_kbps", 0.0), 2),
            round(dados_segmento.get("download_time_s", 0.0), 3),
            round(dados_segmento.get("jitter_network_ms", 0.0), 2),
            round(dados_segmento.get("jitter_ewma_ms", 0.0), 2),
            round(dados_segmento.get("buffer_level_s", 0.0), 2),
            
            # Dados cruciais do BufferManager
            dados_segmento.get("buffer_can_play", 0),
            dados_segmento.get("rebuffer_event", 0),
            round(dados_segmento.get("stall_duration_s", 0.0), 2),
            
            dados_segmento.get("failover_total", 0)
        ]

        # Abre em modo 'a' (append) para adicionar uma linha no final do arquivo sem apagar o resto
        with open(self.filename, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(linha)