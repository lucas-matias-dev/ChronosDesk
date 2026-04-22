//--- CONSTANTES ---
#define MAX_TAREFAS 10

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