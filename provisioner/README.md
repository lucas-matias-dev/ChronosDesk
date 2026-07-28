# Provisionador do ChronosDesk

O provisionador oferece dois fluxos independentes:

- `python main.py`: preserva o provisionamento Spotify via OAuth 2.0 com PKCE
  e USB serial;
- `python main.py google-calendar-test`: valida no computador o OAuth do
  Google Agenda e lista os compromissos do dia, sem usar serial ou ESP32.

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
autoriza chamadas por curto período; o refresh token permitiria obter novos
access tokens sem novo login. Nesta fase ambos permanecem somente em memória e
são descartados ao encerrar o processo: nenhum token é salvo em arquivo,
enviado pela serial ou gravado na NVS.

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

## Segurança

- não compartilhe o JSON OAuth, `.env`, access token ou refresh token;
- não habilite logs HTTP detalhados com headers de autorização;
- o fluxo Google não persiste tokens e não inicializa a serial;
- o fluxo Spotify continua sendo o único que comunica credenciais ao ESP32;
- o callback de ambos os fluxos usa somente loopback e existe apenas durante
  a autorização.
