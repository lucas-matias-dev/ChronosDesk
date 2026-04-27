#include <ArduinoJson.h> 
#include <HTTPClient.h>
#include "config.h"
#include <WiFiClientSecure.h>

//--- CONSTANTES ---
#define MAX_TAREFAS 10

float teste_tickers() {
  WiFiClientSecure client; // Cria o cliente de segurança
  client.setInsecure();    // Pula a verificação de certificados (Modo "Just Run")
  
  HTTPClient http;
  
  // 1. URL precisa do HTTPS://
  String url = "https://script.google.com/macros/s/AKfycbzT__wW5daX1O_aXrbQZU5FQRk0cvXbp-6cXnbOne2kxqXRUPJM_KpGRh0_2kf3YziN/exec?key="+ API_KEY_GOOGLE;
  
  // 2. Passar o 'client' dentro do begin
  delay(2000); 
  http.begin(client, url); 
  
  // 3. ESSENCIAL para Google Apps Script
  http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS); 
  delay(2000); 
  int httpCode = http.GET();
  float preco = 0.0;

  if (httpCode > 0) {
    String payload = http.getString();
    delay(2000);   
    // ArduinoJson V7
    JsonDocument doc;
    delay(2000); 
    deserializeJson(doc, payload);
    delay(2000); 
    // Acessa o dado (certifique-se que o nome da chave está igual ao do GAS)
    preco = doc["XPML11"]["valor_atual"]; 
  } else {
    Serial.printf("Erro HTTP: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  return preco;
}
//--- CLASSES ---
class Tarefa {
  public: 
    // Atributos
    String descricao;
    bool concluida;

    // Método
    void exibir() {
      Serial.print("Descricao: ");
      Serial.println(descricao);
      Serial.print("Status: ");
      Serial.println(concluida ? "Concluida" : "Pendente");
      Serial.println("-------------------");
    }
};

//--- INSTANCIAÇÃO ---
Tarefa listaTarefa[MAX_TAREFAS]; // Array de objetos
int totalDeTarefas = 5;          // Quantas tarefas queremos usar

//--- LÓGICA ---
void teste() {
  // i < totalDeTarefas para não passar do limite
  for (int i = 0; i < totalDeTarefas; i++) {
    listaTarefa[i].descricao = "Tarefa de teste " + String(i + 1);
    listaTarefa[i].concluida = true;
  }

  Serial.println("--- LISTANDO TAREFAS ---");

  for (int i = 0; i < totalDeTarefas; i++) {
    //É pedido para o objeto se exibir
    listaTarefa[i].exibir(); 
  }
}