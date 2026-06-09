import time
import urllib.request
from client import StreamingClient
from abr2 import PredictiveBufferABR
from buffer_manager import BufferManager
from metrics import MetricsLogger
import plot2  

def checar_saude_servidor(url_servidor):
    url_health = url_servidor.rstrip('/') + "/health"
    try:
        with urllib.request.urlopen(url_health, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False

def obter_prioridade(servidor):
    return servidor.get("priority", 0)

def buscar_representacao(lista_reps, qualidade_alvo):
    for rep in lista_reps:
        if rep["quality"] == qualidade_alvo:
            return rep
    return lista_reps[0]

def run_policy_2():
    MANIFEST_URL = "http://137.131.178.229:8080/manifest"
    TOTAL_SEGMENTS = 10

    client = StreamingClient(MANIFEST_URL)
    manifest = client.fetch_manifest()
    
    if not manifest:
        print("Manifesto falhou. Encerrando.")
        return

    SEGMENT_DURATION_S = manifest.get("segment_duration_s", 2.0)
    
    abr = PredictiveBufferABR(manifest)
    buffer = BufferManager()
    logger = MetricsLogger("streaming_metrics_p2.csv") 

    servidores = sorted(manifest["servers"], key=obter_prioridade)
    idx_servidor_atual = 0
    failover_total = 0
    last_throughput = 0.0

    print("\n" + "="*50)
    print("STARTING STREAMING (PREDICTIVE BUFFER-BASED)")
    print("="*50 + "\n")

    for segment_number in range(1, TOTAL_SEGMENTS + 1):
        print(f"\n--- Requesting Segment {segment_number} ---")
        
        current_buffer = buffer.get_current_level()
        selected_quality = abr.get_next_quality(current_buffer, last_throughput)
        rep = buscar_representacao(manifest["representations"], selected_quality)
        
        sucesso_download = False
        
        # Download e Failover
        while not sucesso_download and idx_servidor_atual < len(servidores):
            servidor = servidores[idx_servidor_atual]
            segment_url = servidor["url"] + rep["url_path"]
            
            size, download_time_s, throughput_kbps = client.download_segment(segment_url)
            
            if size == 0: 
                print(f"[FAILOVER] Queda no Servidor {servidor.get('id', 'Atual')}!")
                proximo_idx = idx_servidor_atual + 1
                migrou = False
                
                while proximo_idx < len(servidores):
                    candidato = servidores[proximo_idx]
                    if checar_saude_servidor(candidato["url"]):
                        idx_servidor_atual = proximo_idx
                        failover_total += 1
                        migrou = True
                        print(f"[FAILOVER] Conectado ao Servidor {candidato.get('id')}")
                        break
                    proximo_idx += 1
                
                if not migrou:
                    print("[FAILOVER] Fim da linha. Nenhum servidor reserva.")
                    break
            else:
                sucesso_download = True
                last_throughput = throughput_kbps
                
        if not sucesso_download:
            print("Interrupção crítica do Stream.")
            break
            
        # Atualiza o buffer com o download concluído
        buffer_can_play, rebuffer_event, stall_duration_s = buffer.update_buffer(download_time_s, SEGMENT_DURATION_S)

        dados_segmento = {
            "segment": segment_number,
            "server_id": servidores[idx_servidor_atual].get("id", "A"),
            "quality": selected_quality,
            "bitrate_kbps": rep["bitrate_kbps"],
            "throughput_kbps": throughput_kbps,
            "download_time_s": download_time_s,
            "buffer_level_s": buffer.get_current_level(),
            "buffer_can_play": buffer_can_play,
            "rebuffer_event": rebuffer_event,
            "stall_duration_s": stall_duration_s,
            "failover_total": failover_total
        }
        logger.log_segment(dados_segmento)
        
        # ---------------------------------------------------------------------
        # O SEGREDO DO CONSUMO REALISTA: A FASE "OFF" DO PLAYER
        # Se o buffer chegar a 8.0s, o player "descansa" e deixa o vídeo rodar.
        # Isso vai consumir o buffer perfeitamente no seu gráfico!
        # ---------------------------------------------------------------------
        if buffer.get_current_level() >= 8.0:
            tempo_descanso = 4.0 # Segundos de vídeo assistido sem baixar nada
            print(f"[Player] Buffer cheio! Pausando downloads e assistindo por {tempo_descanso}s...")
            buffer.buffer_level_s -= tempo_descanso
            
        time.sleep(0.5)

    print("\nStreaming Política 2 concluído!")
    print("\nGerando gráfico da Política 2...")
    plot2.generate_chart("streaming_metrics_p2.csv")

if __name__ == "__main__":
    run_policy_2()