import urllib.request
import json
import urllib.error
import time  # <--- Nova importação necessária para medir o tempo

class StreamingClient:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.manifest_data = None

    def fetch_manifest(self):
        """
        (Código da etapa anterior - Mantido igual)
        Faz o download do manifest JSON do servidor.
        """
        print(f"Buscando manifest em: {self.manifest_url}")
        try:
            with urllib.request.urlopen(self.manifest_url) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    self.manifest_data = json.loads(data)
                    print("Manifest carregado com sucesso!\n")
                    return self.manifest_data
                else:
                    print(f"Erro: Servidor retornou status {response.status}")
                    return None
        except Exception as e:
            print(f"Erro ao conectar ao servidor: {e}")
            return None

    def download_segment(self, segment_url):
        """
        Baixa um segmento de vídeo da URL fornecida e calcula a vazão da rede.
        Retorna uma tupla contendo: (tamanho_bytes, tempo_download_s, vazao_kbps)
        """
        # 1. Marca o tempo inicial exato (em segundos desde a época Unix)
        start_time = time.time()
        
        try:
            # Inicia o download
            with urllib.request.urlopen(segment_url) as response:
                if response.status == 200:
                    # Lê todos os bytes do segmento (conteúdo bruto)
                    segment_data = response.read()
                    
                    # 2. Marca o tempo final exato assim que o último byte chega
                    end_time = time.time()
                    
                    # 3. Calcula o tamanho em Bytes
                    tamanho_bytes = len(segment_data)
                    
                    # 4. Calcula o tempo decorrido (T final - T inicial)
                    tempo_download_s = end_time - start_time
                    
                    # 5. Prevenção de erro: se o download for rápido demais (tempo zero)
                    if tempo_download_s == 0:
                        tempo_download_s = 0.001 
                    
                    # 6. Calcula a Vazão em Kilobits por segundo (kbps)
                    # Fórmula: (Bytes * 8 = Bits) / 1000 = Kilobits
                    # Vazão (kbps) = Kilobits / Tempo em segundos
                    tamanho_bits = tamanho_bytes * 8
                    tamanho_kilobits = tamanho_bits / 1000
                    vazao_kbps = tamanho_kilobits / tempo_download_s
                    
                    print(f"Segmento baixado! "
                          f"Tamanho: {tamanho_bytes} bytes | "
                          f"Tempo: {tempo_download_s:.3f} s | "
                          f"Vazão: {vazao_kbps:.2f} kbps")
                          
                    return tamanho_bytes, tempo_download_s, vazao_kbps
                
                else:
                    print(f"Erro ao baixar segmento: HTTP {response.status}")
                    return 0, 0, 0
                    
        except urllib.error.URLError as e:
             print(f"Erro de rede ao baixar segmento: {e}")
             return 0, 0, 0