# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

WaitingRm is a Docker Compose stack that gates a self-hosted Ollama LLM backend behind Telegram identity verification. No inbound ports are exposed — the Telegram bot long-polls outbound, and LAN clients reach the gateway directly via HTTPS.

## Running the Stack

```bash
cp .env.example .env        # fill in BOT_TOKEN, LAN_IP, ALLOWED_USER_IDS, MINI_APP_URL
docker compose up --build   # first run generates self-signed TLS cert automatically
docker compose up -d        # subsequent runs
docker compose logs -f      # tail all service logs
docker compose logs -f auth-validator  # single service
```

## Services & Responsibilities

| Service | Source | Port | Role |
|---|---|---|---|
| `nginx` | `./nginx/` | 8443 (HTTPS), 8080 (redirect) | TLS gateway, static Mini App host, `auth_request` router |
| `auth-validator` | `./auth/` | 5000 (internal only) | Telegram `initData` HMAC verification |
| `telegram-bot` | `./bot/` | none | Long-poll bot, delivers Mini App button |
| `ollama` | upstream image | internal only | LLM inference backend |
| `open-webui` | upstream image | internal only | Optional browser UI at `/webui/` |

## Network Isolation Model

This is the most critical architectural detail:

- `internal_net` has `internal: true` — containers on it have **zero outbound internet routing**
- `nginx` is on `internal_net` but has published ports — LAN traffic reaches it via host port binding (not the network)
- `telegram-bot` has **no `networks:` clause** — lands on Docker's default bridge, has internet for Telegram polling, cannot see `internal_net` services
- For Docker Swarm: change `internal_net.driver` to `overlay` and pre-create with `docker network create --driver overlay --internal internal_net`

## Auth Flow

Every `/api/` request goes through Nginx `auth_request`:

```
Client request → nginx → sub-request to /_auth/validate (internal)
                              → auth-validator checks X-Telegram-Init-Data header
                              → verifies HMAC-SHA256 per Telegram spec
                              → checks auth_date (rejects if >24h old)
                              → checks user ID against ALLOWED_USER_IDS
                         ← 200 OK (with X-User-Id header) or 401/403
              → nginx strips auth headers, forwards X-User-Id to ollama
```

The `initData` HMAC key is derived as `HMAC-SHA256("WebAppData", bot_token)` — per [Telegram spec](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app). This is verified in `auth/app.py:_derive_secret_key()`.

## TLS Certificate

Nginx auto-generates a self-signed cert on first boot via `nginx/entrypoint.sh`. The cert covers `LAN_IP` as a SAN. The cert is persisted in the `nginx_certs` Docker volume — it won't regenerate on restart.

To regenerate: `docker volume rm openclaw_nginx_certs` then restart.

The Mini App HTML (`nginx/www/index.html`) must have `GATEWAY` set to `https://YOUR_LAN_IP:8443`. Users must accept the self-signed cert once in their browser before the Telegram Mini App WebView will connect.

## Modifying the Mini App

The Mini App is a single self-contained file: `nginx/www/index.html`. It:
- Reads `tg.initData` from Telegram's WebApp JS SDK (only present inside Telegram)
- Sends it as `X-Telegram-Init-Data` header on every fetch to the gateway
- Maintains conversation history array for multi-turn Ollama `/api/chat` calls
- Streams responses via `ReadableStream` — expects Ollama's NDJSON streaming format

The Mini App must be hosted on HTTPS (Telegram requirement). Deploy `nginx/www/index.html` to Cloudflare Pages, Vercel, or GitHub Pages — then set `MINI_APP_URL` in `.env`.

## Adding a New Protected Route

1. Add a `location` block in `nginx/openclaw.conf`
2. Include `auth_request /_auth/validate;` in the block
3. Strip auth headers before proxying: `proxy_set_header X-Telegram-Init-Data "";`
