# Auditoria de recursos do ChronosDesk

Data da auditoria: 2026-07-26. Branch inspecionada: `chore/auditoria-recursos`.
O working tree estava limpo antes da primeira alteração. Nenhum commit, push,
upload ou alteração de branch foi realizado. Arquivos locais de credenciais
foram deliberadamente excluídos da leitura e dos logs.

## 1. Resumo executivo

O firmware cabe com folga no ESP32-S3 N16R8. A compilação de referência ocupa
1.091.971 B de um slot de aplicação de 3.145.728 B (34,71%), deixando
2.053.757 B. O linker contabiliza 50.956 B de RAM estática (15,55% de
327.680 B), deixando 276.724 B para heap e stacks dentro desse domínio de
memória. Isso não representa os 8 MiB de PSRAM.

Não há `malloc`, `calloc`, `realloc`, `new`, `delete`, `ps_malloc` ou
`heap_caps_malloc` no código do projeto. O principal risco dinâmico vem
indiretamente de `String`, ArduinoJson, HTTP e mbedTLS. As operações Spotify
recriam clientes HTTPS e documentos JSON a cada consulta; isso libera os
recursos ao sair da função, mas pode produzir picos e fragmentação ao longo do
tempo. Não foi encontrado um vazamento determinístico no código da aplicação.

O módulo condicional `ResourceMonitor` foi adicionado para medir no hardware o
que não pode ser obtido corretamente por análise estática: heap livre/mínimo,
PSRAM detectada/livre/mínima, maiores blocos, indicador de fragmentação, NVS e
high-water mark das tarefas. Desativado (padrão), seu custo medido é 4 B de
flash e 0 B de RAM estática em relação à referência. Ativado, a primeira
compilação de medição ocupou 1.098.051 B de flash e 52.260 B de RAM estática,
isto é, cerca de +6,1 KiB e +1,3 KiB.

## 2. Configuração confirmada

- Placa/módulo: ESP32-S3 DevKitC-1, ESP32-S3 N16R8.
- FQBN: `esp32:esp32:esp32s3`.
- Opções: `FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,USBMode=hwcdc,CDCOnBoot=cdc`.
- Arduino CLI: 1.1.1.
- Arduino Core ESP32: 3.3.11.
- Bibliotecas: Adafruit ST7735/ST7789 1.11.0, Adafruit GFX 1.12.6,
  Adafruit BusIO 1.17.4, ArduinoJson 7.4.3; SPI, Wire, Networking,
  WiFi, HTTPClient, NetworkClientSecure e Preferences 3.3.11.
- `loopTask`: core 1, prioridade 1 e stack configurada de 8.192 B pela
  configuração padrão do core. O projeto não cria tarefas FreeRTOS próprias.
- PSRAM: modo OPI habilitado na compilação. A capacidade física informada é
  8 MiB; detecção e disponibilidade reais exigem execução no dispositivo.
- Alocador: `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=4096`. Em termos práticos,
  alocações menores que 4 KiB tendem a preferir RAM interna; alocações maiores
  podem usar PSRAM. A localização exata continua dependente das capacidades
  pedidas e do estado do heap.
- Watchdog de tarefas: habilitado, timeout de 5 s, com pânico habilitado.
- Compilação com `--warnings all`: a referência e a versão final (1.091.975 B
  de firmware e 50.956 B de RAM estática) não apresentam
  erros. O monitor foi ajustado após um aviso de formato detectado na primeira
  compilação diagnóstica.

## 3. Flash, seções e RAM estática

| Item | Bytes | KiB | Observação |
|---|---:|---:|---|
| Firmware (`ESP.getSketchSize` equivalente do build) | 1.091.971 | 1.066,38 | 34,71% do slot |
| BIN de aplicação | 1.092.112 | 1.066,52 | inclui alinhamento/cabeçalho |
| Slot de aplicação | 3.145.728 | 3.072,00 | cada slot OTA |
| Livre no slot | 2.053.757 | 2.005,62 | 65,29% |
| `.flash.text` | 818.960 | 799,77 | código executado da flash |
| `.flash.rodata` | 151.580 | 148,03 | constantes |
| `.iram0.text` + vetores | 81.723 | 79,81 | código/vetores em IRAM |
| `.dram0.data` | 23.020 | 22,48 | dados inicializados |
| `.dram0.bss` | 27.936 | 27,28 | dados zerados |
| RAM estática total | 50.956 | 49,76 | `.data + .bss` |

Os artefatos analisados foram o ELF (15.672.384 B), MAP (16.702.224 B),
BIN (1.092.112 B), BIN de partições (3.072 B), BIN mesclado de 16 MiB e o
CSV efetivamente copiado pelo build. Seções `dummy` e dados de depuração do ELF
não representam ocupação adicional no dispositivo.

## 4. Tabela real de partições

| Nome | Tipo/subtipo | Início | Tamanho | Finalidade | OTA |
|---|---|---:|---:|---|---|
| `nvs` | data/nvs | `0x009000` | 20 KiB | Preferences, Wi-Fi e metadados | não |
| `otadata` | data/ota | `0x00E000` | 8 KiB | seleção/estado OTA | suporte |
| `app0` | app/ota_0 | `0x010000` | 3 MiB | firmware ativo/candidato | sim |
| `app1` | app/ota_1 | `0x310000` | 3 MiB | segundo slot de firmware | sim |
| `ffat` | data/fat | `0x610000` | 10.354.688 B (9,875 MiB) | FFat | não |
| `coredump` | data/coredump | `0xFF0000` | 64 KiB | diagnóstico de crash | não |

Logo, o esquema é realmente OTA-capaz: há dois slots de 3 MiB. O espaço
destinado ao sistema de arquivos é 9,875 MiB, mas o espaço livre dentro dele
não pode ser informado sem montar/consultar o FFat no hardware. O firmware
atual não monta FFat. A NVS tem 20 KiB; quantidade de entradas usadas/livres é
registrada pelo monitor em runtime.

## 5. Heap, PSRAM e fragmentação

Os números abaixo dependem do dispositivo e **não foram medidos**. O monitor
registra, em bytes, e no boot também em KiB/MiB:

- heap geral: total, livre, mínimo livre e maior alocação;
- RAM interna 8-bit: total, livre, usada, percentual, mínimo e maior bloco;
- PSRAM 8-bit: os mesmos campos;
- heap 8-bit agregado;
- PSRAM física detectada pelas APIs `ESP`;
- uso de NVS e partições vistas em runtime.

O indicador impresso é `maior_bloco_livre / memória_livre * 100`. Um valor
alto sugere boa continuidade; uma queda persistente, especialmente com heap
livre estável, sugere fragmentação. Isoladamente ele não prova fragmentação:
reservas por capacidade, caches de rede e alocações simultâneas também alteram
o resultado. O pico de uso é calculável como `total - mínimo_livre`.

## 6. Tarefas e stacks

O código da aplicação roda na `loopTask`; não há `xTaskCreate` no projeto.
Com diagnóstico ativo, `uxTaskGetSystemState()` lista até 32 tarefas do
sistema com nome, prioridade, núcleo e menor stack livre, e imprime
separadamente a stack configurada e o high-water mark corrente da `loopTask`.
O array de amostragem é estático (não consome a stack observada).

As tarefas Wi-Fi, TCP/IP, eventos, timers e idle são criadas pelas bibliotecas
e pelo core; nomes e stacks exatos variam em runtime. Não se deve reduzir
stack com base apenas numa amostra curta. Estado: não medido até receber o log
de uma execução de pelo menos 8 horas.

## 7. Alocações, buffers e ciclos de vida

| Local | Objeto/tamanho estimado | Vida e memória provável | Risco/recomendação |
|---|---|---|---|
| `SpotifyApiService::fetchCurrentPlayback` | `NetworkClientSecure`, `HTTPClient`, filtro e `JsonDocument` | por requisição; controles em RAM interna e buffers TLS dinâmicos | pico alto/moderado; medir antes/depois de HTTPS |
| `SpotifyApiService::parsePlayback` | documento JSON filtrado e `String artists` | por polling; heap, normalmente interna para blocos pequenos | fragmentação moderada; manter parsing por stream |
| `BoundedStream` | limite lógico de 24.576 B | não armazena toda a resposta; limita bytes lidos | saudável; evita resposta sem limite |
| `SpotifyAuthService::refreshAccessToken` | clientes TLS/HTTP, `String body`, resposta e JSON | por renovação | pico alto porém raro; medir e considerar escrita em stream no futuro |
| `SpotifyCredentials` | `String refreshToken` e `String scopes` | persistente após provisionamento | baixo; necessário e pequeno |
| `SpotifyAuthService` | `String accessToken` | duração do token | baixo/moderado; capacidade pode permanecer alocada após troca |
| `SpotifyPlayback` | ID 48 B, título 64 B, artista 64 B + campos | persistente, tamanho fixo, RAM interna | baixo, sem fragmentação |
| `AppController::updateSpotify` | cópia de playback e `itemBefore[48]` | stack durante consulta | baixo; contribui para pico de stack |
| Provisionamento serial | linha de 2.049 B + documentos JSON | persistente/por mensagem | atenção à stack/heap; tamanho é limitado |
| UI/data-hora | buffers locais até 21 B | stack e curta duração | baixo |
| fontes do display | tabelas constantes | flash/rodata | baixo; fontes futuras podem aumentar flash |
| certificados raiz | duas cópias de cerca de 1.295 B | rodata/flash | baixo; duplicação observada no ELF |

Não há framebuffer completo: a biblioteca desenha no ST7735 por SPI. Não há
armazenamento de álbum nem de resposta JSON integral no fluxo
`currently-playing`; título e artista são copiados para arrays limitados.
O `String artists` faz concatenações em loop e pode realocar. Se os logs de
8 horas indicarem degradação, a primeira otimização é montar o texto
diretamente em buffer fixo, sem mudar o protocolo.

Clientes HTTPS são criados/destruídos em cada polling (5 s). Isso é funcional
e simplifica recuperação, mas torna TLS o principal pico transitório. A
ausência de `setInsecure()` foi preservada.

## 8. Maiores símbolos do ELF

Lista global por tamanho, obtida com `xtensa-esp32s3-elf-nm
--print-size --size-sort --radix=d --demangle`; `T/t` é código,
`D/d` dado inicializado e `B/b` BSS:

| # | Bytes | Tipo | Símbolo |
|---:|---:|:---:|---|
| 1 | 11.413 | T | `_vfprintf_r` |
| 2 | 11.222 | T | `_svfprintf_r` |
| 3 | 7.529 | T | `__ssvfiscanf_r` |
| 4 | 7.473 | T | `_svfiprintf_r` |
| 5 | 5.470 | T | `mbedtls_ssl_handshake_server_step` |
| 6 | 4.192 | D | `port_IntStack` |
| 7 | 4.098 | T | `hostap_recv_mgmt` |
| 8 | 4.040 | T | `mbedtls_ssl_handshake_client_step` |
| 9 | 3.880 | B | `g_cnxMgr` |
| 10 | 3.848 | T | `nd6_input` |
| 11 | 3.618 | T | `tcp_input` |
| 12 | 3.478 | t | `tcp_receive` |
| 13 | 3.223 | T | `_dtoa_r` |
| 14 | 3.189 | T | `scan_parse_beacon` |
| 15 | 3.096 | T | `ieee80211_sta_new_state` |
| 16 | 2.771 | t | `__strftime` |
| 17 | 2.736 | T | `wifi_nvs_cfg_init` |
| 18 | 2.663 | T | `sta_recv_mgmt` |
| 19 | 2.520 | B | `application` |
| 20 | 2.486 | T | `wifi_softap_set_config` |
| 21 | 2.461 | T | `mbedtls_high_level_strerr` |
| 22 | 2.385 | T | `wpa_sm_rx_eapol` |
| 23 | 2.181 | t | `mbedtls_x509_crt_parse_der_internal` |
| 24 | 2.142 | T | `SpotifyApiService::parsePlayback` |
| 25 | 2.096 | T | `mbedtls_ssl_read_record` |
| 26 | 2.054 | T | `ieee80211_parse_rsn` |
| 27 | 2.051 | T | `rmt_new_tx_channel` |
| 28 | 1.952 | d | `ciphersuite_definitions` |
| 29 | 1.919 | T | `HTTPClient::setCookie` |
| 30 | 1.906 | T | `i2cSlaveInit` |

Entre os símbolos do projeto, destacam-se
`SpotifyApiService::parsePlayback` (2.142 B de texto) e
`SpotifyAuthService::refreshAccessToken` (1.823 B). O ELF não contém uma
seção de PSRAM estaticamente ocupada pela aplicação; `.ext_ram.dummy` é
reserva de layout, não 1 MiB consumido.

## 9. Checkpoints e estabilidade

O monitor cobre: início do setup, Serial, display, antes/depois do Wi-Fi,
antes/depois de NTP, token antes/HTTPS/JSON, currently-playing
antes/HTTPS/JSON, atualização relevante de UI, troca de item, pausa/retomada,
erros HTTP/conexão, 401/403/429 e reconexão Wi-Fi. Há resumo a cada 60 s com
contadores de reconexões, requisições, falhas Spotify e erros HTTP. Não há log
em cada passagem rápida do loop.

Plano recomendado:

1. Executar boot sem provisionamento e boot provisionado.
2. Observar token inicial e renovação; manter credenciais fora do log.
3. Exercitar reprodução contínua, pausa/retomada, trocas rápidas e Spotify
   fechado (incluindo resposta 204).
4. Simular perda/retorno de Wi-Fi, DNS inválido e falha HTTPS.
5. Validar 401 e 429 apenas com meios controlados, sem imprimir tokens.
6. Executar primeiro por 1 hora e depois por 8 horas.
7. Comparar os checkpoints de boot, após TLS/JSON e os resumos: mínimos de
   heap/PSRAM, maiores blocos, stacks, contadores e eventuais resets.

Sinais de vazamento: queda monotônica do livre após cada requisição sem
recuperação; queda contínua do maior bloco; mínimo sendo renovado
constantemente; reinicializações. Um mínimo baixo mas estável é pico, não
necessariamente vazamento.

## 10. Capacidade futura

Estimativas são ordens de grandeza e dependem de formato, biblioteca e volume:

| Expansão | Flash | RAM interna | PSRAM/FFat | TLS/conexões | Risco e estratégia |
|---|---|---|---|---|---|
| Letras simples | +10–30 KiB | +1–4 KiB | 8–64 KiB | 1 API | moderado; streaming/cache |
| Letras sincronizadas | +20–60 KiB | +4–12 KiB | 20–150 KiB | 1 API | moderado; índice compacto |
| Cache de letras | +5–20 KiB | <2 KiB | FFat 1–20 MiB | reduz rede | baixo; LRU no FFat |
| Capa do álbum | +20–80 KiB | +8–30 KiB | 50–500 KiB/imagem | download TLS | alto; decode em faixas para PSRAM |
| Framebuffer completo 160×128×16 | pequeno | evitar | ~40 KiB | nenhuma | moderado; alocar em PSRAM |
| Double buffering | pequeno | evitar | ~80 KiB | nenhuma | moderado; PSRAM e DMA por blocos |
| Fontes maiores | +20–200 KiB | <5 KiB | opcional FFat | nenhuma | baixo/moderado; subconjuntos |
| UTF-8 | +10–100 KiB | +1–8 KiB | fonte opcional | nenhuma | moderado; decoder limitado |
| Google Calendar | +30–100 KiB | +10–40 KiB pico | cache 10–100 KiB | novo TLS | alto; serializar integrações |
| Previsão do tempo | +20–60 KiB | +5–20 KiB | cache pequeno | novo TLS | moderado; polling espaçado |
| Cotação | +15–40 KiB | +3–12 KiB | mínimo | novo TLS | moderado; endpoint compacto |
| Métricas do computador | +10–40 KiB | +2–10 KiB | mínimo | LAN/TLS | baixo/moderado; protocolo limitado |
| Métricas do servidor | +15–50 KiB | +3–15 KiB | cache pequeno | rede | moderado; agregação |
| OpenAI | +30–100 KiB | +15–60 KiB pico | resposta/cache | TLS e respostas grandes | alto; proxy e streaming |
| Menus/múltiplas telas | +20–100 KiB | +2–15 KiB | opcional | nenhuma | baixo/moderado; estados estáticos |
| Configurações locais | +5–20 KiB | <5 KiB | NVS/FFat | nenhuma | baixo; versionar esquema |
| Histórico de músicas | +10–40 KiB | +2–10 KiB | FFat crescente | nenhuma extra | moderado; log circular |

Flash e PSRAM têm boa margem. RAM interna e maior bloco contínuo serão os
limitadores para múltiplas conexões TLS simultâneas. Prioridades:

1. Executar e guardar os logs de 1 h/8 h antes de ampliar funcionalidades.
2. Evitar TLS concorrente; encerrar uma integração antes de iniciar outra.
3. Usar streaming e PSRAM para imagens/respostas grandes; buffers compatíveis
   com DMA continuam em RAM interna quando necessário.
4. Trocar concatenações repetidas de `String` apenas se as métricas mostrarem
   fragmentação crescente.
5. Para FFat, adicionar montagem e medição de espaço somente quando houver
   funcionalidade que realmente use o sistema de arquivos.

## 11. Reprodução e coleta no hardware

Compilação normal:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,USBMode=hwcdc,CDCOnBoot=cdc" .
```

Compilação diagnóstica:

```powershell
arduino-cli compile --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,USBMode=hwcdc,CDCOnBoot=cdc" --build-property "compiler.cpp.extra_flags=-DENABLE_RESOURCE_DIAGNOSTICS=1" .
```

Upload (substituir `COMx` pela porta correta, sem mudar opções):

```powershell
arduino-cli upload -p COMx --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,USBMode=hwcdc,CDCOnBoot=cdc" .
arduino-cli monitor -p COMx -c baudrate=115200
```

Após 1 h e 8 h, copiar todas as linhas que começam exatamente com:

```text
[RESOURCE][CHIP]
[RESOURCE] flash_
[RESOURCE] sketch_
[RESOURCE] heap_
[RESOURCE] psram_
[RESOURCE][PARTITION]
[RESOURCE][NVS]
[RESOURCE][TASK
[RESOURCE][CHECKPOINT]
[RESOURCE] region=
[RESOURCE][COUNTERS]
```

Não copiar linhas de provisionamento nem qualquer credencial.

## 12. Quadro final

| Recurso | Total | Uso atual | Pico de uso | Livre | Maior bloco | Status |
|---|---:|---:|---:|---:|---:|---|
| Flash física | 16 MiB | não aplicável | não aplicável | por partições | não aplicável | saudável |
| Slot app0/app1 | 3 MiB cada | 1.091.971 B | estático | 2.053.757 B | não aplicável | saudável |
| RAM estática | 327.680 B (domínio do linker) | 50.956 B | 50.956 B | 276.724 B | não aplicável | saudável |
| Heap interno | runtime | não medido | não medido | não medido | não medido | não medido |
| PSRAM física | 8 MiB informados | não medido | não medido | não medido | não medido | não medido |
| PSRAM detectada | não medido | não medido | não medido | não medido | não medido | não medido |
| FFat | 10.354.688 B | não medido/não montado | não medido | não medido | não aplicável | não medido |
| NVS | 20 KiB | não medido | não medido | não medido | por entradas | não medido |
| Stack `loopTask` | 8.192 B | não medido | não medido | high-water mark pendente | não aplicável | não medido |
