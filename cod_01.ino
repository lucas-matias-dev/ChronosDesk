// ==========================================
//                BIBLIOTECAS
// ==========================================

//--- GRÁFICOS E HARDWARE DA TELA ---
#include <Adafruit_GFX.h>      // Biblioteca "mãe" de gráficos. Fornece funções de desenho.
#include <Adafruit_ST7735.h>  // Driver específico para o chip ST7735 da sua tela.
#include <SPI.h>              // Protocolo de comunicação serial (Serial Peripheral Interface).

//--- REDE (WIFI) ---
#include <Network.h>          // Interface de rede genérica do ESP32, gerencia as camadas de conexão).
#include <WiFi.h>             // Biblioteca principal para configurar o Wi-Fi, conectar em roteadores, senhas.).
#include <esp_wifi.h>         // Funções de baixo nível, usada para ajustar a potência do sinal WIFI).

//--- CONTROLE DO CHIP (HARDWARE) ---
#include <soc/soc.h>          // Definições de hardware do ESP-32 acesso a registros internos do ESP32.
#include <soc/rtc_cntl_reg.h> // Registro de controle do RTC. Usamos para desativar o sensor de Brownout.

//--- CONTROLE DE HORARIO ---
#include "time.h" // Biblioteca padrão do C para manipulação de tempo

//--- SENHAS E CONFIGURAÇÕES ---
#include "config.h"

// ==========================================
//    CONFIGURAÇÕES DE HARDWARE (PINOS)
// ==========================================

#define TFT_CS   5   // CS
#define TFT_RS   2   // RS (também chamado de DC)
#define TFT_RES  4   // RES (também chamado de RESET)

// ==========================================
//            DEFININDO VARIAVEIS
// ==========================================
//--- CONSTANTES ---
const char* servidorNTP = "pool.ntp.org"; // Servidor mundial
const long  gmtOffset_sec = -10800;       // -3h em segundos
const int   daylightOffset_sec = 0;       // Sem horário de verão

//--- VARIAVEIS ---
int ultimoMinuto = -1; 

//--- STRUCT ---
struct tm infoTempo;

// Inicializa o objeto da tela
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_RS, TFT_RES);

//Aqui estamos conectando com o WIFI
void conectarWifi(){
  Network.begin();
  WiFi.STA.begin();
  WiFi.mode(WIFI_STA);

  //defino a potencia do sinal
  esp_wifi_set_max_tx_power(40);
  WiFi.STA.connect(WIFI_SSID, WIFI_PASS);


  // Testando a conexão, nesse caso haverá 10 "tentativas"
  for (int16_t i = 0; i<=10; i++) {
    delay(1000);
    if (WiFi.STA.hasIP()){
      Serial.println("conexão bem sucedida");
      break;
    } 
    else {
      Serial.println("conectando no WIFI...");
    }
  }

  // Definir Wi-Fi como interface padrão
  Network.setDefaultInterface(WiFi.STA);

  // Obter a interface padrão atual
  NetworkInterface *defaultIf = Network.getDefaultInterface();
  Serial.print("Default interface: ");
  Serial.println(defaultIf->impl_name());
}

//função para obtee o horario atual em segundos 
//recebido em segundos decorridos desde 01-01-1970.
void obterHorario() {
  Serial.println("Sincronizando horário com NTP...");

  // Configura o fuso horário e inicia a busca automática
  configTime(gmtOffset_sec, daylightOffset_sec, servidorNTP);
  delay(500);
  if(!getLocalTime(&infoTempo)){
    return;
  }
  delay(500);
  Serial.println("Horário sincronizado com sucesso!");
}

//função para formatar o horario.
String obterHoraFormatada() {
  //struct tm infoTempo;
  delay(1000);
  if(!getLocalTime(&infoTempo)){
    return "00:00"; // Fallback caso falhe
  }
  char bufferHora[9];

  // strftime formata o tempo: %H (hora), %M (minuto)
  strftime(bufferHora, sizeof(bufferHora), "%H:%M", &infoTempo);
  return String(bufferHora);
}

//função para desenhar a interface base
void desenharInterfaceBase(){
  // 1. Limpa a tela
  tft.fillScreen(ST7735_BLACK);

  // 2. Cabeçalho
  tft.setTextSize(1);
  tft.setTextColor(ST7735_MAGENTA);
  
  int16_t x1, y1;
  uint16_t w, h;
  tft.getTextBounds("ATIVIDADES", 0, 0, &x1, &y1, &w, &h);
  int xDinamico = (tft.width() / 2) - (w / 2);
  
  tft.setCursor(xDinamico, 10);
  tft.print("ATIVIDADES");
  
  // Moldura do título
  tft.drawRoundRect(xDinamico - 4, 10 - 4, w + 8, h + 9, 4, ST7735_WHITE);

  // 3. Linha divisória entre Cabeçalho e Lista
  tft.drawFastHLine(0, 30, tft.width(), ST7735_BLUE);

  // 4. Rodapé: Área reservada para o Status do Wi-Fi/Relógio
  tft.drawFastHLine(0, tft.height() - 19, tft.width(), ST7735_WHITE);
  
  // 5. Lista de Tarefas (Labels fixos)
  tft.setCursor(0, 40);
  tft.setTextColor(ST7735_WHITE);
  tft.println("[ ] Estudar ESP32");
  tft.println("[ ] Atividade C++");
  tft.println("[ ] Atividade SQL");
  tft.println("[ ] Atividade MER");
  tft.println("[ ] Ler livros");
  tft.println("[ ] Tratar o cabelo");
  
  Serial.println("Interface base renderizada.");
}

// função para verificação de wifi (simbolo WIFI)
void verificaWifi() {
  int xWifi = 120;
  int yWifi = tft.height() - 5; 
  uint16_t corStatus = (WiFi.STA.hasIP()) ? ST7735_GREEN : ST7735_RED;

  tft.fillRect(xWifi - 10, yWifi - 10, 20, 15, ST7735_BLACK);

  //Desenho dos Círculos (simbolo pre wifi)
  tft.fillCircle(xWifi, yWifi, 2, corStatus);   
  tft.drawCircle(xWifi, yWifi, 5, corStatus);   
  tft.drawCircle(xWifi, yWifi, 9, corStatus);

  //MÁSCARA MULTIPONTOS, para parecer com simbolo do wifi
  tft.fillRect(xWifi - 10, yWifi + 1, 21, 10, ST7735_BLACK);
  tft.fillTriangle(xWifi, yWifi, xWifi - 10, yWifi, xWifi - 10, yWifi - 10, ST7735_BLACK);
  tft.fillTriangle(xWifi, yWifi, xWifi + 10, yWifi, xWifi + 10, yWifi - 10, ST7735_BLACK);
}

void atualizarRelogioTela(struct tm info) {
  tft.setTextSize(1);
  
  // Para não "encavalar" os números, desenhamos um retângulo preto 
  // exatamente onde a hora fica, antes de escrever a nova.
  tft.fillRect(5, tft.height() - 12, 100, 10, ST7735_BLACK);

  char buffer[20];
  strftime(buffer, sizeof(buffer), "%d/%m/%y  %H:%M", &info);
  
  // Desenha a nova hora
  tft.setCursor(5, tft.height() - 12);
  tft.setTextColor(ST7735_GREEN);
  tft.print(buffer);
  
  Serial.print("Tela atualizada: ");
  Serial.println(buffer);
}

//função semi-principal
void setup() {
  // desativa a proteção eletrica
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  tft.initR(INITR_BLACKTAB);

  desenharInterfaceBase();
  delay(2000); 
  conectarWifi();

  if(WiFi.STA.hasIP()) {
    obterHorario();
  }
  verificaWifi();
}

void loop() {
  //struct tm infoTempo;
  if (getLocalTime(&infoTempo)) {
    if (infoTempo.tm_min != ultimoMinuto) {
      ultimoMinuto = infoTempo.tm_min; // Atualiza o rastreador
      atualizarRelogioTela(infoTempo); // Atualiza a hora
      verificaWifi();                 // Atualiza o ícone de conexão
    }
  }
  delay(1000);
}