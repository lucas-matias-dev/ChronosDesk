//--- CONSTANTES ---
#define MAX_TAREFAS 10

//--- VARIAVEIS ---
int totalDeTarefas = 5;

//--- STRUCTS ---
struct Tarefa {
    String descricao;
    bool concluida;
};

Tarefa listaTarefa [MAX_TAREFAS];
//int totalDeTarefas = 0;
void teste (){
  for (int i = 0; i <= totalDeTarefas && totalDeTarefas >= MAX_TAREFAS; i++){
    listaTarefa[i].descricao = "teste";
    listaTarefa[i].concluida = true;
  }

  for (int i = 0; i <= totalDeTarefas; i++){
    Serial.println(listaTarefa[i].descricao);
    Serial.println(listaTarefa[i].concluida);
  }
}