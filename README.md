# ChronosDesk

**ChronosDesk** é um dashboard IoT inteligente desenvolvido com ESP32. O projeto combina sincronização de dados em tempo real via rede com uma interface gráfica otimizada para displays TFT, focado em produtividade e monitoramento de atividades.

> **Status do Projeto:** Funcional / Em Desenvolvimento

---

## Tecnologias e Hardware

- **Microcontrolador:** ESP32 (Dual-core 240MHz)
- **Display:** TFT ST7735 1.8" (Comunicação via protocolo SPI)
- **Linguagem:** C++ (Framework Arduino)
- **Protocolos:**
  - **NTP (Network Time Protocol):** Sincronização de alta precisão do relógio.
  - **SPI:** Interface serial periférica para controle de alta velocidade do display.
- **Bibliotecas Principais:** 
  - `Adafruit_GFX` (Processamento gráfico)
  - `Adafruit_ST7735` (Driver de hardware)
  - `WiFi` & `Network` (Pilha TCP/IP)

##  Funcionalidades

- [x] **Relógio de Tempo Real:** Sincronização automática via servidores NTP.
- [x] **Status de Conectividade:** Ícone de Wi-Fi dinâmico renderizado via primitivas geométricas (subtração booleana).
- [x] **Gestor de Atividades:** Interface dedicada para listagem de tarefas diárias.
- [x] **Otimização de Memória:** Configurado para partição *Huge APP* (3MB).
- [ ] **Integração Google Calendar:** Sincronização com agenda para exibição de próximos eventos.
- [ ] **Integração Spotify:** Exibição da faixa atual ("Now Playing") e controles básicos via API.
- [ ] **Backend de Integração:** Implementação de middleware (Node.js ou Google Apps Script) para gestão de tokens OAuth2.
- [ ] **Estação Meteorológica:** Monitoramento de Temperatura, Umidade e Pressão Atmosférica via sensor **BME280**.
- [ ] **Monitor de Ambiente:** Sensor de Luminosidade para ajuste automático de brilho do display.
- [ ] **Navegação Física:** Controle de menus e interfaces via **Encoder Rotativo**.
- [ ] **Galeria de Assets:** Leitor de Cartão **MicroSD** para carregamento de ícones e imagens BMP (bypass de memória Flash).
- [ ] **Ticker Financeiro:** Monitoramento em tempo real de Ações e Fundos Imobiliários (FIIs).


## Engenharia e Desafios Técnicos

- **Mitigação de Brownout:** Implementação de bypass no registro `RTC_CNTL_BROWN_OUT_REG` para garantir estabilidade durante picos de transmissão do rádio Wi-Fi.
- **Geometria Computacional:** Renderização de ícones via código puro, utilizando máscaras de triângulos e retângulos para otimização de memória Flash (evitando o uso de Bitmaps pesados).

## Como Executar o Projeto

1. **Configuração da IDE:** Certifique-se de ter o suporte ao ESP32 e as bibliotecas `Adafruit GFX` e `Adafruit ST7735` instaladas.
2. **Particionamento:** Configure em `Ferramentas -> Partition Scheme -> Huge APP (3MB No OTA)`.
3. **Gestão de Credenciais:**
   - Este projeto utiliza um arquivo de configuração separado para segurança.
   - Renomeie o arquivo `config.h.example` para `config.h`.
   - Insira seu SSID, senha do Wi-Fi e chaves de API no arquivo `config.h`.
   - **Nota:** O arquivo `config.h` já está configurado no `.gitignore` para não ser enviado ao repositório.
4. **Upload:** Conecte o ESP32 e realize o upload.

## Estrutura de Arquivos

```text
ChronosDesk/
├── ChronosDesk.ino     # Lógica principal e Máquina de Estados
├── config.h.example    # Template de credenciais e Tickers financeiros
├── symbols.h           # Definições de fontes e ícones geométricos
├── .gitignore          # Filtro de segurança
└── README.md           # Documentação
