# Provisionador Spotify do ChronosDesk

Este programa executa uma autorização OAuth 2.0 com PKCE no Windows e envia
ao ESP32 somente o refresh token, o timestamp da autorização e o scope
concedido. Tokens nunca são gravados em arquivo.

## Preparação

1. Instale Python 3.10 ou mais recente.
2. Execute `python -m pip install -r requirements.txt`.
3. Copie `config.example.env` para `.env`.
4. Informe em `.env` o Client ID do aplicativo Spotify.
5. Cadastre exatamente `http://127.0.0.1:8888/callback` nas Redirect URIs do
   aplicativo no Spotify Developer Dashboard.
6. Grave no firmware o mesmo Client ID em `config.h`.

Somente o scope `user-read-currently-playing` é solicitado. Não crie nem
informe um Client Secret.

## Uso

Feche o Monitor Serial e execute:

```powershell
python main.py --port COM5
```

Se `--port` for omitido, o programa mostra as portas detectadas e pede uma.
O navegador padrão será aberto. Depois da autorização, o callback é recebido
somente em `127.0.0.1`; o servidor local encerra após o callback ou timeout.
O provisionador aguarda a confirmação `storage_complete` do ESP32.

Para apagar as credenciais:

```powershell
python main.py --port COM5 --erase
```

Para trocar a porta do callback, altere também a Redirect URI no Dashboard:

```powershell
python main.py --port COM5 --callback-port 9000
```

Não compartilhe `.env`, tokens, capturas do tráfego serial ou logs sensíveis.
