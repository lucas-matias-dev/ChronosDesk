# Provisionador do ChronosDesk

O provisionador oferece quatro fluxos independentes:

- `python main.py`: preserva o provisionamento Spotify via OAuth 2.0 com PKCE
  e USB serial;
- `python main.py google-calendar-test`: valida no computador o OAuth do
  Google Agenda e lista os compromissos do dia, sem usar serial ou ESP32.
- `python main.py google-calendar-provision --port COMx`: conclui o OAuth
  Google e depois provisiona o ESP32 pela serial;
- `python main.py google-calendar-erase --port COMx`: apaga somente as
  credenciais Google locais, sem OAuth e sem revogação remota.

## Preparação

Use Python 3.10 ou mais recente e o ambiente virtual local:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config.example.env .env
```

Nunca versione `.env`, o JSON OAuth Desktop, tokens ou capturas de tráfego.

## Spotify

Informe `SPOTIFY_CLIENT_ID` em `.env`, cadastre exatamente
`http://127.0.0.1:8888/callback` nas Redirect URIs do aplicativo Spotify e
execute:

```powershell
python main.py --port COM5
```

Se `--port` for omitido, o programa mostra as portas detectadas e pede uma.
Somente o escopo `user-read-currently-playing` é solicitado. O navegador
padrão é aberto, o callback é recebido apenas em `127.0.0.1` e o refresh token
é enviado ao ESP32 após a autorização. Nenhum token é salvo pelo Python.

Para apagar as credenciais Spotify da NVS:

```powershell
python main.py --port COM5 --erase
```

Para trocar a porta do callback, altere também a Redirect URI no Dashboard:

```powershell
python main.py --port COM5 --callback-port 9000
```

Feche o Monitor Serial antes de usar qualquer comando Spotify.

## Teste do Google Agenda no computador

Este teste valida a configuração do Google Cloud, OAuth 2.0 com PKCE, acesso
offline e leitura dos eventos de hoje. Ele usa somente o calendário
`primary`, expande recorrências, ignora eventos cancelados e exibe apenas
título e horário. Descrição, localização, participantes, e-mails, links e IDs
não são solicitados nem exibidos.

O escopo fixo e único é:

```text
https://www.googleapis.com/auth/calendar.events.owned.readonly
```

Esse escopo permite visualizar eventos pertencentes à conta e não permite
criar, editar ou excluir compromissos.

### Pré-requisitos no Google Cloud

1. Ative a Google Calendar API no projeto.
2. Configure o público como externo.
3. Enquanto o aplicativo estiver em Testing, adicione sua Conta Google como
   usuário de teste.
4. Crie um cliente OAuth do tipo **Desktop app**.
5. Baixe o JSON do cliente e mantenha-o fora do repositório, por exemplo na
   pasta Downloads.

Não use credencial Web application, API key, service account ou backend.

### Configuração local

Adicione ao `provisioner/.env`:

```env
GOOGLE_OAUTH_CLIENT_FILE=C:/Users/MEU_USUARIO/Downloads/client_secret_arquivo.json
GOOGLE_CALENDAR_TIMEZONE=America/Sao_Paulo
```

O valor é apenas o caminho para o arquivo. Não copie para `.env` o conteúdo do
JSON, o `client_id` ou o `client_secret`. Caminhos relativos, quando usados,
são resolvidos a partir da pasta do `.env`.

O JSON OAuth identifica o aplicativo Desktop perante o Google. O access token
autoriza chamadas por curto período; o refresh token permite obter novos
access tokens sem novo login. No comando `google-calendar-test`, ambos
permanecem somente em memória e são descartados ao encerrar o processo: esse
comando não abre serial nem grava NVS.

### Execução

O ESP32 não precisa estar conectado. Execute:

```powershell
python .\main.py google-calendar-test
```

O programa abre o navegador padrão e cria temporariamente um callback HTTP
restrito a `127.0.0.1`, em uma porta efêmera. Após escolher a conta, revise o
escopo solicitado e confirme o consentimento. O servidor local encerra após o
callback ou após 180 segundos; o timeout pode ser alterado com:

```powershell
python .\main.py google-calendar-test --timeout 240
```

Uma execução bem-sucedida mostra somente confirmações sanitizadas e os
compromissos:

```text
[GCAL] Autorização concluída com sucesso.
[GCAL] Escopo necessário concedido.
[GCAL] Refresh token recebido: sim.
[GCAL] Compromissos encontrados hoje: 2

15:00 — Atividade acadêmica
19:30 — Estudar
```

Eventos em andamento aparecem como `Agora — Título — até HH:MM`; eventos sem
horário aparecem como `Dia inteiro — Título`. Quando não houver eventos, a
saída será `[GCAL] Sem compromissos para hoje.`

### Erros comuns

- `.env` ou variável ausente: confira se o arquivo está em `provisioner/.env`
  e se `GOOGLE_OAUTH_CLIENT_FILE` foi preenchida.
- Arquivo inexistente, diretório ou JSON inválido: confira apenas o caminho e
  baixe novamente a credencial Desktop se necessário.
- Cliente com tipo incorreto: crie um cliente **Desktop app**, não um cliente
  Web.
- `access_denied` ou autorização cancelada: execute novamente e confirme o
  escopo solicitado.
- HTTP 403: confira se a Calendar API está ativa, se a conta está na lista de
  usuários de teste e se o escopo foi configurado.
- Refresh token não retornado: remova o acesso anterior na Conta Google e
  autorize novamente; o comando já solicita consentimento explícito.
- Timeout: conclua o login dentro do prazo ou aumente `--timeout`.
- Falha de rede, DNS ou TLS: confira conexão, proxy, relógio e certificados do
  sistema antes de tentar novamente.

Em projetos externos com status **Testing**, a autorização e o refresh token
expiram normalmente após sete dias para este escopo. Isso é uma política do
Google, não uma persistência feita pelo ChronosDesk.

Para revogar manualmente, abra sua Conta Google, acesse **Segurança**,
**Conexões de terceiros**, selecione o ChronosDesk e escolha **Remover acesso**.
Depois, uma nova execução solicitará autorização novamente. Consulte a
[documentação de OAuth do Google](https://developers.google.com/identity/protocols/oauth2)
e a [ajuda sobre conexões de terceiros](https://support.google.com/accounts/answer/13533235?hl=pt-BR).

## Fase 5: provisionamento Google no ESP32

O provisionamento reutiliza exatamente o OAuth Google descrito acima, mas não
consulta a Calendar API. A ordem é fixa: configuração local validada, OAuth e
escopo confirmados, refresh token e Client ID validados em memória e, somente
depois, abertura da porta serial. Portanto o ESP32 precisa estar disponível
apenas para a etapa serial; a porta não fica ocupada durante o consentimento no
navegador. Feche o Monitor Serial antes dessa etapa.

Execute a partir da raiz do repositório, substituindo `COMx` pela porta local:

```powershell
python .\provisioner\main.py google-calendar-provision --port COMx
```

O protocolo serial v2 negocia explicitamente o provedor `google_calendar`. O
payload persistente contém apenas versão do formato, Google Client ID, refresh
token, timestamp UTC da autorização e o escopo fixo. O access token e o Client
Secret nunca são enviados. Respostas do ESP32 confirmam apenas provedor,
protocolo e resultado; elas não devolvem credenciais, partes, tamanhos ou hashes.

O firmware valida tipo, provedor, protocolo, sequência, campos e limites antes
de gravar. As credenciais ficam no namespace NVS exclusivo `gcal`, separado de
`spotify`. No reprovisionamento, uma nova credencial é gravada e relida em um
slot inativo antes de se tornar a configuração ativa. Nenhuma operação Google
altera o token, timestamp, escopo, versão ou estado de provisionamento Spotify.

Para apagar somente a configuração Google:

```powershell
python .\provisioner\main.py google-calendar-erase --port COMx
```

O apagamento é local e idempotente: remove o namespace `gcal`, preserva o
namespace `spotify` e não acessa a Conta Google. Ele não equivale a revogação
remota. Quando necessário, revogue manualmente em **Conta Google > Segurança >
Conexões de terceiros**, conforme os links da seção anterior.

Mensagens esperadas são confirmações sanitizadas como autorização validada,
protocolo compatível, `storage_complete` ou `credentials_erased`. Nunca copie
saída serial que contenha material de credenciais.

### Roteiro manual da Fase 5

1. Compile e grave manualmente o firmware com as opções N16R8 já validadas.
2. Feche o Monitor Serial, conecte o ESP32 e identifique a porta local.
3. Confirme localmente o caminho do JSON OAuth no `.env` e ative a `.venv`.
4. Execute `google-calendar-provision --port COMx` e conclua o consentimento.
5. Confirme que nenhum token aparece e que a serial abre somente após o OAuth.
6. Confirme o resultado `storage_complete`, reinicie e valide o Spotify.
7. Reprovisione e confirme a substituição sem impacto no Spotify.
8. Execute `google-calendar-erase --port COMx` duas vezes e confirme o resultado
   idempotente e a continuidade do Spotify.

Nesta fase o ESP32 não renova access token Google, não chama endpoints Google,
não consulta eventos, não implementa TLS/JSON do Calendar, cache, modo offline
da agenda ou integração com o display.

## Segurança

- não compartilhe o JSON OAuth, `.env`, access token ou refresh token;
- não habilite logs HTTP detalhados com headers de autorização;
- `google-calendar-test` não persiste tokens e não inicializa a serial;
- o provisionamento Google persiste somente o material necessário no ESP32;
- Google e Spotify usam namespaces NVS e negociações de provedor separados;
- o callback de ambos os fluxos usa somente loopback e existe apenas durante
  a autorização.
