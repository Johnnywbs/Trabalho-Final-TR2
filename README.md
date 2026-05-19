# Cliente de Streaming Adaptativo (ABR)

Uma simulação em Python de um cliente de streaming ABR (Adaptive Bitrate). O cliente baixa segmentos de vídeo de um servidor, ajustando dinamicamente o nível de qualidade com base nas condições da rede em tempo real, enquanto rastreia o estado do buffer e registra métricas de desempenho.

---

## Estrutura do Projeto

```
├── main.py             # Ponto de entrada — orquestra o loop completo de streaming
├── client.py           # Cliente HTTP para buscar o manifest e baixar segmentos
├── abr.py              # Algoritmo ABR — decide o nível de qualidade de cada segmento
├── buffer_manager.py   # Simula o buffer de reprodução do vídeo
├── metrics.py          # Registra métricas por segmento em um arquivo CSV
└── plot.py             # Gera um gráfico a partir dos dados do CSV
```

---

## Como Funciona

O cliente simula o que um player de vídeo real faz durante o streaming: ele baixa segmentos de vídeo continuamente, um por um, decidindo em tempo real se deve transmitir em alta qualidade (quando a conexão está rápida) ou reduzir para uma qualidade menor (quando a conexão está lenta), tudo isso tentando evitar que o buffer se esgote e cause travamentos.

### Fluxo Passo a Passo

```
1. Buscar manifest       → descobrir as qualidades disponíveis e a URL do servidor
2. Para cada segmento:
   a. ABR decide a qualidade → baseado na vazão medida recentemente
   b. Baixar segmento         → medir tempo de download e vazão real
   c. Atualizar histórico ABR → registrar a nova vazão na janela deslizante
   d. Atualizar buffer        → simular a variação do nível do buffer
   e. Registrar métricas      → gravar uma linha no CSV
3. Gerar gráfico         → visualizar vazão vs. qualidade ao longo do tempo
```

---

## Módulos em Detalhe

### `main.py` — Orquestrador

O ponto de entrada do projeto. Instancia todos os componentes e executa o loop de download dos segmentos.

**Constantes principais:**
| Constante | Valor | Descrição |
|---|---|---|
| `MANIFEST_URL` | `http://…:8080/manifest` | Endereço do manifest no servidor de streaming |
| `TOTAL_SEGMENTS` | `10` | Número de segmentos a serem baixados |
| `SEGMENT_DURATION_S` | lido do manifest (padrão `2.0`) | Duração de cada segmento de vídeo em segundos |

**Lógica do loop por segmento:**
1. Pedir ao ABR a melhor qualidade → `abr.get_next_quality()`
2. Localizar a URL de download dessa qualidade no manifest
3. Baixar o segmento → `client.download_segment(segment_url)`
4. Informar a vazão medida ao ABR → `abr.record_throughput()`
5. Atualizar a simulação do buffer → `buffer.update_buffer()`
6. Gravar todas as métricas do segmento no CSV → `logger.log_segment()`

---

### `client.py` — Cliente HTTP (`StreamingClient`)

Responsável por toda comunicação de rede, usando o módulo `urllib` da biblioteca padrão do Python.

#### `fetch_manifest()`
Faz uma requisição GET para a `MANIFEST_URL` e interpreta a resposta JSON. O manifest descreve as representações de qualidade disponíveis e a URL base do servidor. Estrutura esperada:

```json
{
  "segment_duration_s": 2.0,
  "servers": [{ "url": "http://....:8080" }],
  "representations": [
    { "quality": "1080p", "bitrate_kbps": 4500, "url_path": "/segment/1080p" },
    { "quality": "720p",  "bitrate_kbps": 2500, "url_path": "/segment/720p"  },
    { "quality": "480p",  "bitrate_kbps": 1000, "url_path": "/segment/480p"  },
    { "quality": "240p",  "bitrate_kbps": 400,  "url_path": "/segment/240p"  }
  ]
}
```

#### `download_segment(segment_url)`
Baixa um segmento e mede o desempenho da rede:

```
vazão (kbps) = (tamanho_bytes × 8 / 1000) / tempo_download_s
```

Um valor mínimo de `0.001s` é aplicado ao `download_time_s` para evitar divisão por zero em conexões locais extremamente rápidas.

Retorna `(size_bytes, download_time_s, throughput_kbps)`.

---

### `abr.py` — Algoritmo de Bitrate Adaptativo (`RateBasedABR`)

Implementa um algoritmo **ABR Baseado em Taxa (Rate-Based)**. O objetivo é sempre escolher a maior qualidade cujo bitrate caiba confortavelmente dentro da capacidade de rede estimada.

#### Parâmetros
| Parâmetro | Padrão | Descrição |
|---|---|---|
| `safety_factor` | `0.8` | Multiplicador aplicado à vazão média para criar uma margem de segurança (80%) |
| `window_size` | `3` | Número de segmentos recentes mantidos no histórico de vazão |

#### `record_throughput(throughput_kbps)`
Adiciona a medição mais recente a uma janela deslizante. Quando a janela ultrapassa `window_size`, a entrada mais antiga é descartada. Isso faz com que o ABR reaja rapidamente a mudanças na rede sem ser impactado por um único valor atípico.

#### `get_next_quality()`
Lógica de decisão:

```
1. Se não há histórico → retornar a menor qualidade (padrão seguro)
2. Calcular a média da janela deslizante
3. Aplicar a margem de segurança:  vazão_segura = média × safety_factor
4. Iterar os níveis de qualidade do maior para o menor bitrate
5. Retornar o primeiro nível cujo bitrate_kbps ≤ vazão_segura
6. Se nenhum couber → retornar a menor qualidade (último recurso)
```

O fator de segurança (0.8) significa que o algoritmo só escolhe uma qualidade cujo bitrate utiliza no máximo 80% da capacidade estimada, deixando margem para flutuações na vazão.

**Exemplo:**

```
Vazão recente:   [3000, 2800, 3200] kbps
Média:           3000 kbps
Vazão segura:    2400 kbps  (3000 × 0.8)
Qualidade:       720p requer 2500 kbps? Não. 480p requer 1000 kbps? Sim → 480p
```

---

### `buffer_manager.py` — Simulação de Buffer (`BufferManager`)

Modela o buffer de reprodução — o estoque de conteúdo pré-baixado que mantém o player rodando sem interrupções mesmo que a rede sofra instabilidades momentâneas.

#### Estado
| Atributo | Descrição |
|---|---|
| `buffer_level_s` | Profundidade atual do buffer em segundos de vídeo |
| `total_rebuffer_events` | Total de travamentos ocorridos durante a sessão |
| `total_stall_duration_s` | Tempo total acumulado de congelamento em segundos |

#### `update_buffer(download_time_s, segment_duration_s)`

O núcleo da simulação. Modela dois eventos simultâneos que acontecem a cada download:

```
Fase 1 — Consumo:
  Enquanto o download leva download_time_s, o player continua reproduzindo.
  buffer_level -= download_time_s

Fase 2 — Verificação de travamento:
  Se buffer_level < 0:
    → O vídeo travou. stall_duration = abs(buffer_level)
    → buffer_level é redefinido para 0

Fase 3 — Reabastecimento:
  O download terminou. O novo conteúdo é adicionado ao buffer.
  buffer_level += segment_duration_s
```

Retorna `(buffer_can_play, rebuffer_event, stall_duration_s)`.

**Cenário A — Rede rápida (sem travamento):**
```
buffer antes:    4.0s
download:        0.5s  → buffer cai para 3.5s  (sem travamento)
segmento add:    2.0s  → buffer sobe para 5.5s
```

**Cenário B — Rede lenta (com travamento):**
```
buffer antes:    1.0s
download:        3.0s  → buffer cai para -2.0s  (travou por 2.0s!)
stall_duration:  2.0s, buffer redefinido para 0.0s
segmento add:    2.0s  → buffer sobe para 2.0s
```

---

### `metrics.py` — Logger CSV (`MetricsLogger`)

Grava uma linha por segmento em `streaming_metrics.csv`. O arquivo é (re)criado do zero toda vez que o cliente inicia.

#### Colunas do CSV

| Coluna | Tipo | Descrição |
|---|---|---|
| `segment` | int | Número de sequência do segmento (1, 2, 3, …) |
| `timestamp` | string ISO 8601 | Horário de relógio quando o segmento foi registrado |
| `server_id` | string | Identificador do servidor (padrão `"A"`) |
| `quality` | string | Rótulo de qualidade escolhido pelo ABR (ex: `"720p"`) |
| `bitrate_kbps` | int | Bitrate nominal da qualidade escolhida |
| `throughput_kbps` | float | Vazão de rede real medida |
| `download_time_s` | float | Tempo gasto para baixar o segmento |
| `jitter_network_ms` | float | Jitter de rede por segmento (reservado, padrão `0`) |
| `jitter_ewma_ms` | float | Jitter suavizado por EWMA (reservado, padrão `0`) |
| `buffer_level_s` | float | Nível do buffer após o processamento do segmento |
| `buffer_can_play` | int | `1` se a reprodução foi contínua, `0` se travou |
| `rebuffer_event` | int | `1` se houve travamento neste segmento |
| `stall_duration_s` | float | Duração do travamento em segundos (`0` se não houve) |
| `failover_total` | int | Número de failovers de servidor (reservado, padrão `0`) |

---

### `plot.py` — Gerador de Gráfico

Lê `streaming_metrics.csv` e produz um gráfico de duas linhas salvo como `baseline_chart.png`.

- **Linha azul tracejada** — vazão de rede real por segmento
- **Linha laranja em degrau** — nível de qualidade (bitrate) escolhido pelo ABR por segmento
- **Rótulos** — nome da qualidade (ex: `480p`) anotado acima de cada ponto laranja

O gráfico em degrau (`plt.step`) é intencional: a qualidade não sobe em rampa — ela muda abruptamente de um nível para outro entre segmentos.

---

## Arquivos de Saída

| Arquivo | Gerado por | Descrição |
|---|---|---|
| `streaming_metrics.csv` | `MetricsLogger` | Log de desempenho por segmento |
| `baseline_chart.png` | `plot.py` | Visualização de vazão vs. qualidade |

---

## Como Executar

```bash
python main.py
```

Isso irá:
1. Buscar o manifest no servidor
2. Baixar 10 segmentos, imprimindo o progresso no terminal
3. Salvar `streaming_metrics.csv`
4. Gerar e exibir `baseline_chart.png`

Para regenerar o gráfico a partir de um CSV existente sem re-baixar os segmentos:

```bash
python plot.py
```

---

## Dependências

| Biblioteca | Usada em | Finalidade |
|---|---|---|
| `urllib` | `client.py` | Requisições HTTP (biblioteca padrão) |
| `csv` | `metrics.py`, `plot.py` | Leitura/escrita de CSV (biblioteca padrão) |
| `datetime` | `metrics.py` | Timestamps ISO 8601 (biblioteca padrão) |
| `matplotlib` | `plot.py` | Geração de gráficos (terceiro) |

Instalar dependências de terceiros:

```bash
pip install matplotlib
```
