import time
from client import StreamingClient
from abr import RateBasedABR, BufferBasedABR
from buffer_manager import BufferManager
from metrics import MetricsLogger
import plot

def obter_prioridade(servidor):
    return servidor.get("priority", 0)

def buscar_representacao(lista_representacoes, qualidade_desejada):
    for rep in lista_representacoes:
        if rep["quality"] == qualidade_desejada:
            return rep
    return lista_representacoes[-1]

def run_simulation(policy_type="P1", output_csv="streaming_metrics.csv"):
    MANIFEST_URL = "http://137.131.178.229:8080/manifest"
    TOTAL_SEGMENTS = 10

    client = StreamingClient(MANIFEST_URL)
    manifest = client.fetch_manifest()

    if not manifest:
        print("Erro: Manifesto não pôde ser carregado.")
        return

    SEGMENT_DURATION_S = manifest.get("segment_duration_s", 2.0)
    
    # Usa o SEU gerenciador de buffer original, intocado!
    buffer = BufferManager()
    logger = MetricsLogger(output_csv)

    lista_servidores = sorted(manifest["servers"], key=obter_prioridade)
    current_server_idx = 0
    failover_count = 0

    if policy_type == "P1":
        abr = RateBasedABR(manifest)
        print("\n" + "="*40 + "\nINICIANDO POLÍTICA 1 (RATE-BASED)\n" + "="*40)
    else:
        # Histerese: Se o buffer passar de 4.0s, ele sobe a qualidade gradualmente
        abr = BufferBasedABR(manifest, min_buf_s=2.5, max_buf_s=4.0)
        print("\n" + "="*40 + "\nINICIANDO POLÍTICA 2 (BUFFER-BASED)\n" + "="*40)

    for segment_number in range(1, TOTAL_SEGMENTS + 1):
        print(f"\n--- Segmento {segment_number}/{TOTAL_SEGMENTS} ---")
        
        # O ABR lê o buffer (agora ele vai crescer naturalmente a cada iteração)
        current_buffer = buffer.get_current_level()
        
        if policy_type == "P1":
            selected_quality = abr.get_next_quality()
        else:
            selected_quality = abr.get_next_quality(current_buffer)

        selected_rep = buscar_representacao(manifest["representations"], selected_quality)
        nominal_bitrate = selected_rep["bitrate_kbps"]
        url_path = selected_rep["url_path"]

        # Loop de Download + Mecanismo de Failover Automatizado
        download_success = False
        while not download_success and current_server_idx < len(lista_servidores):
            server_info = lista_servidores[current_server_idx]
            server_url = server_info["url"]
            server_id = server_info.get("id", str(current_server_idx))
            
            segment_url = server_url + url_path
            
            size, download_time_s, throughput_kbps, network_failed = client.download_segment(segment_url)

            if network_failed:
                print(f"[FAILOVER] Servidor {server_id} falhou!")
                procurar_proximo = True
                proximo_idx = current_server_idx + 1
                
                while procurar_proximo and proximo_idx < len(lista_servidores):
                    candidato = lista_servidores[proximo_idx]
                    print(f"[FAILOVER] Testando Health Check: {candidato['url']}")
                    
                    if client.check_health(candidato["url"]):
                        current_server_idx = proximo_idx
                        failover_count += 1
                        procurar_proximo = False
                        print(f"[FAILOVER] Migrado para o Servidor {candidato.get('id')}")
                    else:
                        proximo_idx += 1
                
                if procurar_proximo:
                    print("[FAILOVER] Nenhum servidor saudável restante na lista.")
                    break
            else:
                download_success = True

        if not download_success:
            print("Interrupção crítica: Transmissão incapaz de baixar dados.")
            break

        if policy_type == "P1":
            abr.record_throughput(throughput_kbps)
            
        # O seu BufferManager processa os tempos reais. Como o download_time (ex: 0.17s) 
        # é menor que a duração do segmento (2.0s), o saldo será positivo e o buffer acumula!
        buffer_can_play, rebuffer_event, stall_duration_s = buffer.update_buffer(download_time_s, SEGMENT_DURATION_S)

        segment_data = {
            "segment": segment_number,
            "server_id": lista_servidores[current_server_idx].get("id", "A"),
            "quality": selected_quality,
            "bitrate_kbps": nominal_bitrate,
            "throughput_kbps": throughput_kbps,
            "download_time_s": download_time_s,
            "buffer_level_s": buffer.get_current_level(),
            "buffer_can_play": buffer_can_play,
            "rebuffer_event": rebuffer_event,
            "stall_duration_s": stall_duration_s,
            "failover_total": failover_count
        }
        logger.log_segment(segment_data)
        time.sleep(0.1)

if __name__ == "__main__":
    run_simulation(policy_type="P1", output_csv="metrics_p1.csv")
    run_simulation(policy_type="P2", output_csv="metrics_p2.csv")

    print("\nProcessando gráficos sobrepostos...")
    plot.compare_policies_chart("metrics_p1.csv", "metrics_p2.csv")