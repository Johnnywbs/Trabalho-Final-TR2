import time
import urllib.request
from client import StreamingClient
from buffer_manager import BufferManager
from metrics import MetricsLogger
from abr import RateBasedABR
from abr_v2 import BufferBasedABR

# ==========================================
# FLAG DE SELEÇÃO DE POLÍTICA
# False = Política 1 (Baseline Rate-Based)
# True  = Política 2 (Buffer-Based Histerese)
# ==========================================
USE_POLICY_V2 = True

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

def run_client():
    MANIFEST_URL = "http://137.131.178.229:8080/manifest"
    TOTAL_SEGMENTS = 10

    client = StreamingClient(MANIFEST_URL)
    manifest = client.fetch_manifest()
    
    if not manifest:
        print("Manifesto falhou. Encerrando o experimento.")
        return

    SEGMENT_DURATION_S = manifest.get("segment_duration_s", 2.0)
    
    buffer = BufferManager()
    
    if USE_POLICY_V2:
        print("\n" + "="*50 + "\nSTARTING STREAMING: POLÍTICA 2 (BUFFER-BASED)\n" + "="*50)
        # parâmetros para a sensibilidade do buffer (quanto menor mais agressivo)
        abr = BufferBasedABR(manifest, buffer, panic_buf=1.0, down_buf=2.0, up_buf=3.0)
        arquivo_csv = "streaming_metrics_p2.csv"
    else:
        print("\n" + "="*50 + "\nSTARTING STREAMING: POLÍTICA 1 (RATE-BASED BASELINE)\n" + "="*50)
        abr = RateBasedABR(manifest)
        arquivo_csv = "streaming_metrics.csv"
        
    logger = MetricsLogger(arquivo_csv) 
    servidores = sorted(manifest["servers"], key=obter_prioridade)
    idx_servidor_atual = 0
    failover_total = 0

    for segment_number in range(1, TOTAL_SEGMENTS + 1):
        print(f"\n--- Requesting Segment {segment_number} ---")
        
        selected_quality = abr.get_next_quality()
        rep = buscar_representacao(manifest["representations"], selected_quality)
        
        sucesso_download = False
        
        while not sucesso_download and idx_servidor_atual < len(servidores):
            servidor = servidores[idx_servidor_atual]
            segment_url = servidor["url"] + rep["url_path"]
            
            size, download_time_s, throughput_kbps = client.download_segment(segment_url)
            
            if size == 0: 
                print(f"[FAILOVER] Queda detectada no servidor!")
                proximo_idx = idx_servidor_atual + 1
                migrou = False
                
                while proximo_idx < len(servidores):
                    candidato = servidores[proximo_idx]
                    if checar_saude_servidor(candidato["url"]):
                        idx_servidor_atual = proximo_idx
                        failover_total += 1
                        migrou = True
                        print(f"[FAILOVER] Migrado para o servidor reserva: {candidato.get('id')}")
                        break
                    proximo_idx += 1
                
                if not migrou:
                    break
            else:
                sucesso_download = True
                
        if not sucesso_download:
            print("Falha crítica na rede. Impossível continuar.")
            break
            
        abr.record_throughput(throughput_kbps)
        
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
        
        # =======================
        # SIMULAÇÃO DE REPRODUÇÃO
        # =======================
        LIMITE_TETO = 8.0     # Quando atinge esse valor, o player pausa os downloads
        LIMITE_RECARGA = 4.0  # Quando cai para esse valor, o player volta a baixar

        if buffer.get_current_level() >= LIMITE_TETO:
            print(f"\n[Player] Teto de buffer atingido ({LIMITE_TETO}s). Interrompendo rede (Fase OFF).")
            
            # Laço iterativo que consome 1 segundo do buffer por vez
            while buffer.get_current_level() > LIMITE_RECARGA:
                passo_consumo = 1.0
                buffer.buffer_level_s -= passo_consumo
                print(f"   ▶ Reproduzindo vídeo... Restante no buffer: {buffer.get_current_level():.2f}s")
                time.sleep(0.5)
                
            print("[Player] Nível de recarga atingido. Reativando requisições de rede (Fase ON).")
        else:
            time.sleep(0.2)

    print(f"\nTransmissão concluída. Dados armazenados em: {arquivo_csv}")

if __name__ == "__main__":
    run_client()
    
    print("\nRenderizando os gráficos de análise...")
    
    if USE_POLICY_V2:
        import plot2 
        plot2.generate_chart("streaming_metrics_p2.csv")
    else:
        import plot 
        plot.generate_throughput_quality_chart("streaming_metrics.csv")