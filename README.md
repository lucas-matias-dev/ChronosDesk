# ChronosDesk

ChronosDesk é um dashboard de mesa para ESP32-S3 com display ST7735. O
firmware mantém relógio, data e status de Wi-Fi e consulta diretamente a
Spotify Web API para mostrar a reprodução atual.

Depois do provisionamento inicial, o dispositivo funciona sem o computador:

```text
Spotify no navegador ──PKCE──> provisionador Windows ──USB serial──> ESP32-S3
                                                                     │
Operação diária: ESP32-S3 ──HTTPS──> Spotify Accounts / Web API <────┘
```

Não existe backend intermediário, callback no ESP32, Client Secret ou servidor
público. O PC é usado somente para autorizar, reautorizar ou apagar a
configuração.

## Hardware e ambiente validado

- ESP32-S3 DevKitC-1 N16R8;
- 16 MB de flash;
- 8 MB de PSRAM OPI;
- display ST7735 de 1,8 polegada por SPI;
- Arduino-ESP32 3.3.7;
- Python 3.10 ou posterior no Windows para o provisionador.

Pinos do display:

| Sinal | GPIO |
| --- | ---: |
| CS | 5 |
| DC/RS | 2 |
| RESET | 4 |

A proteção de brownout permanece habilitada.

## Dependências

Firmware:

- Adafruit GFX Library 1.12.5;
- Adafruit ST7735 and ST7789 Library 1.11.0;
- Adafruit BusIO 1.17.4;
- ArduinoJson 7.4.3;
- HTTPClient, NetworkClientSecure, Preferences, Wi-Fi, NTP e SPI fornecidos
  pelo core ESP32 3.3.7.

Provisionador:

- Python 3;
- pyserial 3.5.

## Estrutura

```text
cod_01/
├── cod_01.ino
├── provisioner/
│   ├── main.py
│   ├── spotify_auth.py
│   ├── callback_server.py
│   ├── serial_transport.py
│   ├── config.example.env
│   ├── requirements.txt
│   ├── README.md
│   └── tests/
│       └── test_provisioner.py
├── src/
│   ├── app/
│   │   └── AppController.*
│   ├── config/
│   │   ├── AppConfig.h
│   │   ├── Secrets.h
│   │   ├── Secrets.cpp
│   │   └── Secrets.cpp.example
│   ├── display/
│   │   └── DisplayManager.*
│   ├── network/
│   │   └── WiFiService.*
│   ├── spotify/
│   │   ├── SpotifyApiService.*
│   │   ├── SpotifyAuthService.*
│   │   ├── SpotifyCertificates.h
│   │   ├── SpotifyCredentials.h
│   │   ├── SpotifyHttpUtils.*
│   │   ├── SpotifyPlayback.*
│   │   ├── SpotifyProvisioningService.*
│   │   └── SpotifyTokenStorage.*
│   ├── time/
│   │   └── TimeService.*
│   └── ui/
│       └── SpotifyView.*
├── README.md
└── .gitignore
```

`src/config/Secrets.cpp` e `provisioner/.env` são arquivos locais ignorados
pelo Git. Os respectivos arquivos de exemplo podem ser versionados com
segurança.

## Responsabilidades

- `AppController`: coordena Wi-Fi, hora, autenticação, consultas e view.
- `SpotifyTokenStorage`: valida e persiste refresh token, timestamp, scopes e
  versão em NVS por meio de `Preferences`.
- `SpotifyProvisioningService`: recebe mensagens JSON pela USB serial sem
  bloquear o loop.
- `SpotifyAuthService`: obtém e renova access tokens. Access tokens permanecem
  somente na RAM.
- `SpotifyApiService`: chama `/v1/me/player/currently-playing`, limita e
  interpreta somente os campos necessários.
- `SpotifyPlayback`: modelo pequeno, sem JSON ou dependência gráfica.
- `SpotifyView`: apresenta título, artista, play/pause, tempos, barra e estados.
- `WiFiService`, `TimeService` e `DisplayManager`: preservam as
  responsabilidades da arquitetura anterior.

## Configuração local do firmware

Copie o exemplo para criar o arquivo local:

```powershell
Copy-Item .\src\config\Secrets.cpp.example .\src\config\Secrets.cpp
```

Depois preencha somente a cópia `Secrets.cpp`:

```cpp
#include "Secrets.h"

const char* const configuredWiFiSsid = "NOME_DA_REDE";
const char* const configuredWiFiPassword = "SENHA_DA_REDE";
const char* const configuredSpotifyClientId = "CLIENT_ID_DO_APLICATIVO";
```

`Secrets.h` contém apenas declarações usadas pelos serviços.
`Secrets.cpp.example` contém placeholders e serve de modelo versionado.
`Secrets.cpp` contém os valores efetivos do firmware e não deve ser
versionado.

O Client ID não é um segredo criptográfico, mas permanece junto das
configurações locais para não ser espalhado pelos arquivos públicos. Nunca
adicione Client Secret, tokens, senha do Spotify ou código de autorização ao
firmware.

O mesmo Spotify Client ID deve ser informado em `src/config/Secrets.cpp` e
em `provisioner/.env`. Não preencha access token ou refresh token
manualmente: eles são obtidos pelo provisionador, e o refresh token é
armazenado na NVS do ESP32.

O antigo `config.h` não é mais incluído pelo firmware. Ele e
`config.h.example` são mantidos apenas como artefatos legados; não constituem
uma segunda fonte de configuração. Novas instalações devem usar
exclusivamente `Secrets.cpp` criado a partir de `Secrets.cpp.example`.

Intervalos, limites, timezone e pinos estão em `src/config/AppConfig.h`.

## Criando o aplicativo Spotify

1. Acesse o [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Crie um aplicativo.
3. Nas configurações, cadastre exatamente:

   ```text
   http://127.0.0.1:8888/callback
   ```

4. Copie apenas o Client ID para `src/config/Secrets.cpp` e
   `provisioner/.env`.
5. Não crie nem utilize Client Secret.

O callback precisa corresponder exatamente ao Dashboard. `localhost` não é
aceito; o Spotify exige o endereço de loopback explícito. O único scope
solicitado é:

```text
user-read-currently-playing
```

Em Development Mode, o proprietário do aplicativo precisa atualmente ter
Spotify Premium. Outros usuários precisam estar na allowlist do aplicativo.
Consulte as páginas oficiais sobre
[redirect URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri),
[PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow)
e [quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).

## Compilação para N16R8

Na Arduino IDE, selecione **ESP32S3 Dev Module** e configure:

| Opção | Valor |
| --- | --- |
| Flash Size | 16MB |
| PSRAM | OPI PSRAM |
| Partition Scheme | 16M Flash (3MB APP/9.9MB FATFS) |
| USB Mode | Hardware CDC and JTAG |
| USB CDC On Boot | Enabled |

Depois selecione a porta e envie o sketch. A partição NVS do esquema escolhido
armazena as credenciais persistentes; o FATFS não é usado pelo MVP.

## Provisionamento inicial

No PowerShell:

```powershell
cd provisioner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config.example.env .env
```

Edite `.env`, informe o Client ID e identifique a porta COM pelo Gerenciador
de Dispositivos ou pela lista mostrada pelo programa. Feche o Monitor Serial e
execute:

```powershell
python main.py --port COM5
```

O provisionador:

1. gera `code_verifier`, challenge S256 e `state` aleatórios;
2. abre um servidor temporário somente em `127.0.0.1:8888`;
3. abre a autorização oficial no navegador;
4. valida obrigatoriamente o `state`;
5. troca o código usando PKCE;
6. descarta o access token recebido;
7. envia somente refresh token, timestamp, scope e versão ao ESP32;
8. aguarda `storage_complete`;
9. encerra o servidor e limpa referências sensíveis em memória.

Nenhum token é salvo pelo Python. Consulte também
[provisioner/README.md](provisioner/README.md).

## Protocolo serial

O protocolo 1 usa JSON UTF-8 delimitado por quebra de linha.

| Direção | `type` | Finalidade |
| --- | --- | --- |
| PC → ESP32 | `provision_begin` | Inicia negociação |
| ESP32 → PC | `provision_ready` | Firmware compatível |
| PC → ESP32 | `store_credentials` | Envia dados persistentes |
| ESP32 → PC | `storage_complete` | Confirma NVS |
| ESP32 → PC | `validation_failed` | Dados inválidos |
| ESP32 → PC | `storage_failed` | Falha de NVS |
| ESP32 → PC | `incompatible_version` | Protocolo incompatível |
| PC → ESP32 | `erase_credentials` | Solicita apagamento |
| ESP32 → PC | `credentials_erased` | Confirma apagamento |

O ESP32 nunca devolve o refresh token.

## Operação diária

Com Wi-Fi e horário válido, o ESP32 troca o refresh token por um access token
via `https://accounts.spotify.com/api/token`. O access token usa `expires_in`
da resposta e é renovado dois minutos antes da expiração.

A reprodução é consultada aproximadamente a cada cinco segundos. O progresso
avança localmente a cada segundo enquanto toca e é corrigido na próxima
resposta. Quando pausado, ele não avança.

O firmware trata:

- `200`: item atual;
- `204`: nada tocando;
- `401`: invalida access token e faz uma renovação controlada;
- `403`: autorização/conta indisponível;
- `429`: respeita `Retry-After`;
- `5xx`, DNS, timeout e TLS: backoff exponencial limitado;
- `invalid_grant`: apaga a credencial inválida e pede reautorização.

O Spotify documenta refresh tokens com validade de aproximadamente seis meses.
O timestamp original é preservado para informação, mas `invalid_grant` é a
fonte definitiva. Veja a documentação oficial de
[refresh de tokens](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens),
[reprodução atual](https://developer.spotify.com/documentation/web-api/reference/get-the-users-currently-playing-track)
e [rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits).

## Segurança

- HTTPS valida a cadeia e o hostname usando DigiCert Global Root G2.
- A raiz, não o certificado folha, está fixada no firmware.
- Chamadas Spotify só começam depois de o NTP fornecer horário válido.
- Não existe `setInsecure()`.
- O ESP32 abre somente conexões de saída.
- Não existe callback, servidor administrativo, UPnP ou porta pública nele.
- NVS não possui criptografia neste MVP; acesso físico ao dispositivo pode
  expor o refresh token.
- Secure Boot, Flash Encryption e eFuses não são habilitados nesta etapa.
- Logs nunca incluem tokens, códigos OAuth, senha Wi-Fi ou Authorization.

Se a cadeia de certificados do Spotify mudar para outra raiz, atualize
`SpotifyCertificates.h` a partir de uma fonte oficial antes de compilar.

## Estados no display

- Spotify não configurado;
- conectando;
- sincronizando horário;
- autenticando Spotify;
- tocando;
- pausado;
- nada tocando;
- autorização necessária;
- limite de requisições;
- Spotify indisponível;
- sem Wi-Fi.

Relógio, data e indicador Wi-Fi continuam funcionando durante falhas Spotify.

## Apagar e reautorizar

Feche o Monitor Serial e execute:

```powershell
python provisioner/main.py --port COM5 --erase
```

Depois execute novamente o provisionamento normal. Isso também é necessário
após revogação, expiração do refresh token ou troca do aplicativo Spotify.

## Roteiro de teste no hardware

1. Fazer o provisionamento inicial e observar `storage_complete`.
2. Reiniciar o ESP32 e confirmar que ele obtém um access token sem o PC.
3. Testar faixa tocando, pausada e ausência de reprodução.
4. Desligar o Wi-Fi e verificar relógio/interface responsivos.
5. Restaurar o Wi-Fi e observar recuperação.
6. Apagar a NVS pelo provisionador e confirmar o estado não configurado.
7. Reprovisionar e testar novamente.

## Limitações do MVP

- sem capa do álbum;
- sem controles de reprodução ou volume;
- sem playlists;
- sem backend, OTA ou servidor web;
- título e artista são truncados no display;
- chamadas HTTPS do HTTPClient são síncronas e limitadas por timeout;
- NVS não criptografada;
- certificado raiz precisa de manutenção se a PKI do Spotify mudar.

Todos os arquivos de texto são UTF-8. Nunca publique
`src/config/Secrets.cpp`, `provisioner/.env`, tokens ou logs sensíveis.
