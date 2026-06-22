# Streaming Adaptativo ABR — Trabalho Final TR2

Simulação de um cliente de streaming adaptativo (ABR) sobre HTTP, implementando três políticas de seleção de qualidade, failover automático entre servidores e análise comparativa de desempenho.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Como Rodar](#como-rodar)
- [Políticas ABR](#políticas-abr)
  - [Política 1 — Rate-Based](#política-1--rate-based)
  - [Política 2 — Buffer-Based](#política-2--buffer-based)
  - [Política 3 — EWMA com Penalidade de Jitter](#política-3--ewma-com-penalidade-de-jitter)
- [Infraestrutura](#infraestrutura)
  - [Buffer Manager](#buffer-manager)
  - [Cliente e Failover](#cliente-e-failover)
  - [Métricas CSV](#métricas-csv)
- [Análise e Gráficos](#análise-e-gráficos)
- [Estrutura de Arquivos](#estrutura-de-arquivos)

---

## Visão Geral

O projeto simula um player de vídeo que baixa segmentos de 2 segundos a partir de um servidor HTTP. A cada segmento, a política ABR decide qual resolução baixar com base nas condições de rede e/ou nível do buffer. O sistema suporta dois servidores (A e B) com failover automático quando o servidor primário falha.

**Resoluções disponíveis:**

| Qualidade | Bitrate nominal |
|-----------|----------------|
| 240p      | 200 kbps       |
| 360p      | 400 kbps       |
| 480p      | 600 kbps       |
| 720p      | 900 kbps       |
| 1080p     | 1200 kbps      |

---

## Arquitetura

```
main.py               ← orquestrador principal
├── client.py         ← download HTTP, health check, failover
├── abr.py            ← Política 1: Rate-Based
├── abr_v2.py         ← Política 2: Buffer-Based
├── abr_v3.py         ← Política 3: EWMA + Jitter
├── buffer_manager.py ← simulação do buffer do player
├── metrics.py        ← gravação do CSV por segmento
├── analysis.py       ← análise estatística dos CSVs
└── plot.py           ← geração dos gráficos comparativos
```

Todas as políticas expõem a mesma interface, permitindo que o `main.py` as use de forma intercambiável:

```python
abr.record_throughput(throughput_kbps, jitter_ms)  # registra medição após download
abr.get_next_quality(buffer_level_s)               # retorna resolução para o próximo segmento
```

---

## Como Rodar

### Pré-requisitos

```bash
pip install matplotlib numpy
```

### Executar uma política

```bash
python main.py --politica 1 --segmentos 30   # Rate-Based
python main.py --politica 2 --segmentos 30   # Buffer-Based
python main.py --politica 3 --segmentos 30   # EWMA + Jitter
```

Os aliases `--policy` e `--segments` também funcionam.

### Gerar análise comparativa

Após rodar as três políticas, execute:

```bash
python analysis.py
```

Ou especificando os arquivos CSV diretamente:

```bash
python analysis.py --p1 streaming_metrics_p1.csv \
                   --p2 streaming_metrics_p2.csv \
                   --p3 streaming_metrics_p3.csv
```

A análise imprime uma tabela com todas as métricas e salva os quatro gráficos em `charts/`.

---

## Políticas ABR

### Política 1 — Rate-Based

**Arquivo:** `abr.py`

A política mais simples. Mantém uma janela deslizante das últimas 3 medições de throughput e aplica um fator de segurança fixo de 0.8:

```
estimativa = média(últimas 3 medições) × 0.8
```

Seleciona a maior qualidade cujo bitrate cabe na estimativa. Não usa o nível do buffer para tomar decisões de qualidade — o buffer é gerenciado apenas pelo `BufferManager`.

**Características:**
- Simples e previsível
- Reage com atraso de até 3 segmentos a mudanças de rede
- O fator fixo de 0.8 tende a subestimar a capacidade real da rede, mantendo qualidade conservadora mesmo em redes estáveis

---

### Política 2 — Buffer-Based

**Arquivo:** `abr_v2.py`

Ignora completamente a vazão de rede. Decide a qualidade exclusivamente pelo nível atual do buffer via interpolação linear:

```
razão        = (buffer − 2s) / (12s − 2s)
bitrate_alvo = 200 + razão × (1200 − 200)  kbps
```

| Buffer  | Bitrate alvo | Qualidade típica  |
|---------|-------------|-------------------|
| ≤ 2s    | 200 kbps    | 240p (emergência) |
| 4s      | 400 kbps    | 360p              |
| 7s      | 700 kbps    | 480p              |
| 10s     | 1000 kbps   | 720p              |
| ≥ 12s   | 1200 kbps   | 1080p             |

**Histerese assimétrica** evita oscilações de qualidade:
- **Subir:** 1 confirmação consecutiva
- **Descer:** 2 confirmações consecutivas E buffer < 6s — com buffer confortável, descidas são bloqueadas

**Características:**
- Estável após o buffer encher — resistente a picos de jitter
- Rampa de subida lenta: precisa que o buffer alcance 12s para liberar 1080p (tipicamente 9+ segmentos)
- Não usa nenhuma informação de rede — ignora completamente o throughput medido

---

### Política 3 — EWMA com Penalidade de Jitter

**Arquivo:** `abr_v3.py`

Política híbrida que combina estimativa estatística de rede com consciência do estado do buffer. Implementa dois componentes analíticos obrigatórios da Tarefa 3.

#### Componente 1 — EWMA de Vazão (componente estatístico)

Média Móvel Exponencial com α = 0.4:

```
EWMA_nova = 0.4 × throughput_atual + 0.6 × EWMA_anterior
```

Diferente da média simples da P1, a EWMA dá peso exponencialmente decrescente às amostras antigas. Com α = 0.4, os pesos implícitos são:

| Segmento | Peso  |
|----------|-------|
| atual    | 40%   |
| -1       | 24%   |
| -2       | 14%   |
| -3       | 9%    |
| ...      | ...   |

Isso faz a estimativa reagir mais rápido a mudanças reais de rede, sem supervalorizar picos pontuais como faria uma leitura instantânea. A estimativa de capacidade é:

```
estimativa = EWMA × FATOR_SEGURANCA (0.99)
```

#### Componente 2 — Penalidade de Jitter (tratamento explícito de variação de atraso)

Jitter é o desvio padrão dos intervalos entre chegadas de chunks dentro de um segmento. Jitter alto indica entrega irregular: mesmo que o throughput médio pareça suficiente, os chunks chegam de forma errática — o que pode esgotar o buffer entre chegadas mesmo sem queda de bandwidth.

A penalidade só atua quando **buffer < 6s**, que é o cenário de risco imediato:

```
excesso  = max(0, jitter_EWMA − 25ms)
multiplo = excesso / 25ms
fator    = max(0.70, FATOR_SEGURANCA − multiplo × 0.10)
```

Com buffer alto (≥ 6s), a penalidade é desativada — o buffer absorve a irregularidade de entrega sem necessidade de reduzir qualidade.

Exemplos práticos:

| Jitter EWMA | Buffer | Fator efetivo | Efeito              |
|-------------|--------|---------------|---------------------|
| 15ms        | 3s     | 0.99          | Sem penalidade       |
| 50ms (2×)   | 3s     | 0.89          | Estimativa −10%      |
| 100ms (4×)  | 3s     | 0.70          | Estimativa −29% (piso) |
| 200ms       | 8s     | 0.99          | Buffer alto, sem penalidade |

#### Componente 3 — Bônus de Buffer

Com buffer ≥ 10s, a política sugere um nível de qualidade acima do que a estimativa autorizaria. A lógica é que o buffer acumulado serve de margem de segurança — se o próximo segmento demorar mais que o esperado, o player tem reserva suficiente para absorver sem causar rebuffer:

```
if buffer >= 10s:
    idx_sugerido = idx_atual + 1  # tenta um nível acima
```

A histerese confirma a subida antes de aplicar (evita oscilações).

#### Histerese

- Tolerância = 2 para subir e descer
- Descidas adicionalmente bloqueadas quando buffer ≥ 6s

**Fluxo de decisão por segmento:**

```
1. buffer < 2s?        → 240p imediato (emergência)
2. Atualiza EWMA de vazão e jitter
3. buffer < 6s?        → calcula penalidade de jitter no fator
4. estimativa          = EWMA × fator
5. Seleciona melhor qualidade dentro da estimativa
6. buffer >= 10s?      → sugere um nível acima (bônus)
7. Histerese           → confirma subida/descida (tolerância 2)
```

---

## Infraestrutura

### Buffer Manager

**Arquivo:** `buffer_manager.py`

Simula o buffer de reprodução do player. A cada segmento baixado:

1. **Consumo durante download:** `buffer -= download_time_s`
   - Se buffer zerar antes do download terminar: rebuffer (stall) detectado
2. **Reabastecimento:** `buffer += segment_duration_s`
3. **Pacing de playback:** após o buffer atingir 15s, aguarda `max(0, segment_duration_s − download_time_s)` segundos para simular o ritmo real de reprodução

O pacing é essencial para a simulação ser realista — sem ele, downloads rápidos fariam o buffer crescer indefinidamente e a política nunca precisaria reagir a restrições.

**Parâmetros:**

| Constante         | Valor | Significado                          |
|-------------------|-------|--------------------------------------|
| `BUFFER_MAX_S`    | 20s   | Teto do buffer (pausa o download)    |
| `BUFFER_TARGET_S` | 15s   | Limiar de ativação do pacing         |

### Cliente e Failover

**Arquivo:** `client.py`

- Carrega o manifest via HTTP (lista de servidores e representações disponíveis)
- Downloads em chunks de 4096 bytes com medição de throughput e jitter
- **Detecção de falha rápida:** timeout de conexão de 5s + timeout por chunk idle de 1.5s — se nenhum byte chegar em 1.5s durante o download, aborta imediatamente sem esperar o timeout completo
- **Failover:** ao detectar falha, faz health check no servidor alternativo (`/health`) e migra se disponível

O jitter é calculado como o desvio padrão dos intervalos entre chegadas de chunks:

```python
intervalos = [chunk_times[i] - chunk_times[i-1] for i in range(1, len(chunk_times))]
jitter_ms  = desvio_padrao(intervalos) × 1000
```

### Métricas CSV

**Arquivo:** `metrics.py`

Grava uma linha por segmento com 14 campos:

| Campo                | Descrição                                         |
|----------------------|---------------------------------------------------|
| `segment`            | Número do segmento                                |
| `timestamp`          | Horário do download                               |
| `server_id`          | Servidor usado (A ou B)                           |
| `quality`            | Resolução escolhida                               |
| `bitrate_kbps`       | Bitrate nominal da resolução                      |
| `throughput_kbps`    | Throughput medido no download                     |
| `download_time_s`    | Tempo de download em segundos                     |
| `jitter_network_ms`  | Jitter medido neste segmento                      |
| `jitter_ewma_ms`     | EWMA do jitter (α=0.2, calculada em main.py)      |
| `buffer_level_s`     | Nível do buffer após o segmento                   |
| `buffer_can_play`    | 1 se buffer não zerou, 0 se houve stall           |
| `rebuffer_event`     | 1 se houve rebuffer neste segmento                |
| `stall_duration_s`   | Duração do stall em segundos (0 se não houve)     |
| `failover_total`     | Total acumulado de failovers na sessão            |

---

## Análise e Gráficos

### Análise textual — `analysis.py`

Gera para cada política:
- Número de oscilações de qualidade (trocas consecutivas de resolução)
- Eventos e taxa de rebuffer
- Velocidade de adaptação (segmentos até a qualidade estabilizar por 3 consecutivos)
- Distribuição de qualidade (% do tempo em cada resolução)
- Buffer médio e throughput médio da sessão

E uma tabela comparativa lado a lado entre todas as políticas disponíveis.

### Gráficos — `plot.py`

Todos salvos em `charts/`.

#### `comparison_chart.png`
Dois painéis sobrepostos compartilhando o eixo X (segmentos):
- **Superior:** throughput medido por segmento para cada política (linhas tracejadas)
- **Inferior:** resolução selecionada ao longo do tempo, com eixo Y em resoluções (240p → 1080p)

Linhas verticais vermelhas semitransparentes indicam rebuffers; linhas laranjas pontilhadas indicam failovers.

#### `buffer_chart.png`
Nível do buffer em segundos ao longo dos segmentos para todas as políticas. Marcadores `▼` indicam onde ocorreram rebuffers. Cada evento de failover é marcado com uma cor distinta (vermelho, roxo, marrom, teal).

#### `jitter_chart.png`
EWMA do jitter em ms por segmento para cada política. Útil para correlacionar períodos de alta variação de atraso com quedas de qualidade ou ativação da penalidade de jitter na P3.

#### `quality_dist_chart.png`
Barras agrupadas com a porcentagem de segmentos em cada resolução para cada política. Permite comparar visualmente qual política entrega maior qualidade média ao longo da sessão.

### Resultados típicos (rede estável, 30 segmentos)

| Métrica                  | P1     | P2     | P3     |
|--------------------------|--------|--------|--------|
| 1080p (% do tempo)       | 0%     | 73.3%  | 93.3%  |
| Segmentos até estabilizar | 2      | 9      | 3      |
| Oscilações de qualidade  | 1      | 4      | 1      |
| Rebuffers                | 1      | 1      | 1      |

**Por que P3 é superior:** a EWMA reage mais rápido a uma rede estável que a interpolação de buffer da P2, chegando em 1080p já no segmento 3–5 enquanto P2 precisa encher o buffer até 12s (segmento 9+). A penalidade de jitter protege contra degradação em cenários de entrega irregular com buffer baixo, e o bônus de buffer permite aproveitar a margem acumulada para manter ou subir qualidade após perturbações temporárias.

---

## Estrutura de Arquivos

```
.
├── main.py                    # Ponto de entrada e laço principal de streaming
├── abr.py                     # Política 1 — Rate-Based (média simples × fator fixo)
├── abr_v2.py                  # Política 2 — Buffer-Based (interpolação linear)
├── abr_v3.py                  # Política 3 — EWMA + Penalidade de Jitter
├── buffer_manager.py          # Simulação do buffer do player com pacing
├── client.py                  # Cliente HTTP, health check, failover
├── metrics.py                 # Logger CSV (14 campos por segmento)
├── analysis.py                # Análise estatística comparativa entre políticas
├── plot.py                    # Geração de 4 gráficos comparativos
├── streaming_metrics_p1.csv   # Métricas da última execução da Política 1
├── streaming_metrics_p2.csv   # Métricas da última execução da Política 2
├── streaming_metrics_p3.csv   # Métricas da última execução da Política 3
└── charts/
    ├── comparison_chart.png   # Throughput vs resolução por política
    ├── buffer_chart.png       # Nível do buffer ao longo do tempo
    ├── jitter_chart.png       # EWMA do jitter por segmento
    └── quality_dist_chart.png # Distribuição percentual de resoluções
```
