import urllib.request
import urllib.error
import json
import time


# ---------------------------------------------------------------------------
# Constantes de timeout
# ---------------------------------------------------------------------------
HEALTH_CHECK_TIMEOUT_S     = 3
SEGMENT_DOWNLOAD_TIMEOUT_S = 15
CHUNK_SIZE = 4096

MANIFEST_URL = "http://137.131.178.229:8080/manifest"


SERVER_ID_NORMALIZE = {
    "srv-B": "B",
    "srv-A": "A",
}

def normalizar_id(raw_id: str) -> str:
    """Retorna o ID normalizado para o CSV ('A', 'B', …)."""
    return SERVER_ID_NORMALIZE.get(raw_id, raw_id)


class StreamingClient:
    def __init__(self):
        self.manifest_data  = None
        self.servers        = []   # lista de dicts lida e normalizada do manifest
        self.current_index  = 0
        self.failover_total = 0

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def current_server(self):
        return self.servers[self.current_index]

    @property
    def current_server_url(self):
        return self.current_server["url"]

    @property
    def current_server_id(self):
        return self.current_server["id"]

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def fetch_manifest(self):

        urls_para_tentar = [MANIFEST_URL]

        # Se já temos servidores de uma tentativa anterior, adiciona os demais
        for s in self.servers:
            candidate_url = s["url"].rstrip("/") + "/manifest"
            if candidate_url not in urls_para_tentar:
                urls_para_tentar.append(candidate_url)

        for manifest_url in urls_para_tentar:
            print(f"[Cliente] Tentando manifest em: {manifest_url}")
            try:
                req = urllib.request.Request(manifest_url)
                with urllib.request.urlopen(req, timeout=HEALTH_CHECK_TIMEOUT_S * 2) as resp:
                    if resp.status != 200:
                        print(f"[Cliente] HTTP {resp.status}, tentando próximo…")
                        continue

                    raw = json.loads(resp.read().decode("utf-8"))
                    self.manifest_data = raw

                    # Lê e normaliza a lista de servidores do manifest
                    raw_servers = raw.get("servers", [])
                    self.servers = sorted(
                        [
                            {**s, "id": normalizar_id(s["id"])}
                            for s in raw_servers
                        ],
                        key=lambda s: s.get("priority", 99)
                    )

                    if not self.servers:
                        print("[Cliente] Manifest sem lista de servidores. Encerrando.")
                        return None

                    # Descobre qual servidor respondeu e aponta current_index para ele.
                    # Usa a URL base (sem /manifest) para comparar.
                    base_url_respondeu = manifest_url.rsplit("/manifest", 1)[0]
                    self.current_index = next(
                        (i for i, s in enumerate(self.servers)
                         if s["url"].rstrip("/") == base_url_respondeu.rstrip("/")),
                        0
                    )

                    print(
                        f"[Cliente] Manifest carregado via servidor "
                        f"'{self.current_server_id}' ({self.current_server_url}).\n"
                        f"          Servidores disponíveis: "
                        f"{[(s['id'], s['url']) for s in self.servers]}\n"
                    )
                    return self.manifest_data

            except Exception as exc:
                print(f"[Cliente] {manifest_url} falhou ({exc}), tentando próximo…")

        print("[Cliente] Nenhum servidor conseguiu fornecer o manifest. Encerrando.")
        return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self, server: dict) -> bool:
        url = server["url"].rstrip("/") + "/health"
        try:
            with urllib.request.urlopen(url, timeout=HEALTH_CHECK_TIMEOUT_S) as resp:
                ok = resp.status == 200
                print(f"[HealthCheck] {url} → {'OK' if ok else 'FALHA'} (HTTP {resp.status})")
                return ok
        except Exception as exc:
            print(f"[HealthCheck] {url} → FALHA ({exc})")
            return False

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def _try_failover(self) -> bool:
        """
        Percorre self.servers (lido do manifest) em ordem de prioridade,
        pula o servidor atual e muda para o primeiro que passar no health check.
        """
        for idx, server in enumerate(self.servers):
            if idx == self.current_index:
                continue
            print(f"[Failover] Tentando servidor '{server['id']}': {server['url']} …")
            if self.health_check(server):
                old_id = self.current_server_id
                self.current_index = idx
                self.failover_total += 1
                print(f"[Failover] ✅ Migrado de {old_id} → {self.current_server_id} "
                      f"(failover #{self.failover_total})")
                return True
        print("[Failover] ❌ Nenhum servidor alternativo disponível.")
        return False

    # ------------------------------------------------------------------
    # Download de segmento
    # ------------------------------------------------------------------

    def download_segment(self, segment_url: str, expected_bytes: int = 0):
        """
        Baixa um segmento chunk a chunk com failover automático em caso de falha.

        Retorna:
            size_bytes, download_time_s, throughput_kbps,
            jitter_network_ms, failover_happened
        """
        failover_happened = False

        for _ in range(len(self.servers)):
            url = self.current_server_url.rstrip("/") + "/" + segment_url.lstrip("/")
            resultado = self._download_com_chunks(url, expected_bytes)

            if resultado is not None:
                size, dl_time, tput, jitter = resultado
                return size, dl_time, tput, jitter, failover_happened

            print(f"[Cliente] Download falhou no servidor {self.current_server_id}. "
                  f"Tentando failover…")
            if not self._try_failover():
                break
            failover_happened = True

        print("[Cliente] Todos os servidores esgotados. Retornando segmento vazio.")
        return 0, 0.0, 0.0, 0.0, failover_happened

    def _download_com_chunks(self, url: str, expected_bytes: int = 0):
        """
        Lê a resposta em blocos de CHUNK_SIZE bytes, registrando o timestamp
        de chegada de cada bloco para calcular o jitter_network_ms.

        Retorna (size_bytes, download_time_s, throughput_kbps, jitter_ms)
        ou None em caso de erro.
        """
        chunk_times = []
        total_bytes = 0
        start_time  = time.time()

        try:
            with urllib.request.urlopen(
                urllib.request.Request(url), timeout=SEGMENT_DOWNLOAD_TIMEOUT_S
            ) as resp:
                if resp.status != 200:
                    print(f"[Cliente] HTTP {resp.status} para {url}")
                    return None
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    chunk_times.append(time.time())

        except urllib.error.URLError as exc:
            print(f"[Cliente] Erro de rede: {exc}")
            return None
        except Exception as exc:
            print(f"[Cliente] Erro inesperado: {exc}")
            return None

        if expected_bytes > 0 and total_bytes != expected_bytes:
            print(f"[Cliente] ⚠️  Recebido {total_bytes} B, manifest esperava {expected_bytes} B")

        end_time        = chunk_times[-1] if chunk_times else time.time()
        download_time_s = max(end_time - start_time, 0.001)
        throughput_kbps = (total_bytes * 8 / 1000) / download_time_s

        # Desvio padrão dos intervalos entre chegadas de chunks (jitter intra-segmento)
        jitter_ms = 0.0
        if len(chunk_times) >= 2:
            intervalos_ms = [
                (chunk_times[i] - chunk_times[i - 1]) * 1000
                for i in range(1, len(chunk_times))
            ]
            media     = sum(intervalos_ms) / len(intervalos_ms)
            variancia = sum((g - media) ** 2 for g in intervalos_ms) / len(intervalos_ms)
            jitter_ms = variancia ** 0.5

        print(f"[Cliente] ✔ {total_bytes} B | {download_time_s:.3f}s | "
              f"{throughput_kbps:.1f} kbps | jitter {jitter_ms:.2f} ms | "
              f"chunks: {len(chunk_times)}")

        return total_bytes, download_time_s, throughput_kbps, jitter_ms