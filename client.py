import urllib.request
import json
import urllib.error
import time

class StreamingClient:
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.manifest_data = None

    def fetch_manifest(self):
        print(f"Buscando manifesto em: {self.manifest_url}")
        try:
            with urllib.request.urlopen(self.manifest_url, timeout=5) as response:
                if response.status == 200:
                    data = response.read().decode('utf-8')
                    self.manifest_data = json.loads(data)
                    return self.manifest_data
        except Exception as e:
            print(f"Erro ao carregar manifesto: {e}")
        return None

    def check_health(self, server_url):
        """Realiza um GET simples em /health para checar se o servidor está online."""
        health_url = server_url.rstrip('/') + "/health"
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        return False

    def download_segment(self, segment_url):
        start_time = time.time()
        try:
            with urllib.request.urlopen(segment_url, timeout=5) as response:
                if response.status == 200:
                    segment_data = response.read()
                    end_time = time.time()
                    
                    size_bytes = len(segment_data)
                    download_time_s = max(end_time - start_time, 0.001)
                    throughput_kbps = (size_bytes * 8 / 1000) / download_time_s
                    
                    return size_bytes, download_time_s, throughput_kbps, False
        except Exception as e:
            print(f"[Client] Falha de conexão com o segmento: {e}")
            
        return 0, 0, 0, True  # Retorna True indicando falha na rede