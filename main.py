import time
from client import StreamingClient
from abr import RateBasedABR
from buffer_manager import BufferManager
from metrics import MetricsLogger
import plot # Importaremos o gerador de gráficos no final!

def rodar_cliente():
    # 1. Configurações Iniciais
    URL_MANIFEST = "http://137.131.178.229:8080/manifest"
    DURACAO_SEGMENTO_S = 4.0 # Assumindo 4 segundos de vídeo por segmento
    TOTAL_SEGMENTOS = 10 # Quantidade exigida para a Entrega 1
    
    # 2. Inicializa as nossas ferramentas
    cliente = StreamingClient(URL_MANIFEST)
    manifest = cliente.fetch_manifest()
    
    if not manifest:
        print("Falha ao carregar o manifest. Encerrando.")
        return

    abr = RateBasedABR(manifest)
    buffer = BufferManager()
    logger = MetricsLogger("metricas_streaming.csv")
    
    url_servidor = manifest["servers"][0]["url"]

    print("\n" + "="*50)
    print("INICIANDO STREAMING (BASELINE RATE-BASED)")
    print("="*50 + "\n")

    # 3. O Loop Principal de Download
    for numero_do_segmento in range(1, TOTAL_SEGMENTOS + 1):
        print(f"--- Solicitando Segmento {numero_do_segmento} ---")
        
        # ABR decide a qualidade
        qualidade_escolhida = abr.obter_proxima_qualidade()
        
        # Busca o bitrate nominal dessa qualidade no manifest (para salvar no CSV)
        bitrate_nominal = next(q["bitrate_kbps"] for q in manifest["representations"] if q["quality"] == qualidade_escolhida)
        
        # Monta a URL do vídeo
        # Nota: O formato exato da URL depende do servidor do professor. 
        # Geralmente é algo como: url/qualidade/segment_X.ts
        url_segmento = f"{url_servidor}/{qualidade_escolhida}/segment_{numero_do_segmento}.ts"
        
        # Faz o download e mede a vazão
        tamanho, tempo_s, vazao_kbps = cliente.download_segment(url_segmento)
        
        # Informa a vazão ao ABR para a próxima decisão
        abr.registrar_vazao(vazao_kbps)
        
        # Atualiza o Buffer
        buffer_can_play, rebuffer_event, stall_s = buffer.atualizar_buffer(tempo_s, DURACAO_SEGMENTO_S)
        
        # Prepara e salva os dados no CSV
        dados = {
            "segment": numero_do_segmento,
            "quality": qualidade_escolhida,
            "bitrate_kbps": bitrate_nominal,
            "vazao_kbps": vazao_kbps,
            "download_time_s": tempo_s,
            "buffer_level_s": buffer.get_nivel_atual(),
            "buffer_can_play": buffer_can_play,
            "rebuffer_event": rebuffer_event,
            "stall_duration_s": stall_s
        }
        logger.registrar_segmento(dados)
        
        # Pequena pausa dramática para o terminal não piscar tudo de uma vez
        time.sleep(0.5)

    print("\nStreaming concluído! Arquivo CSV gerado.")

if __name__ == "__main__":
    rodar_cliente()
    
    # 4. Ao final do download, gera o gráfico automaticamente!
    print("Gerando gráficos...")
    plot.gerar_grafico_vazao_qualidade("metricas_streaming.csv")