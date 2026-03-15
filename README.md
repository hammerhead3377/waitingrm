# WaitingRm

> The Doctor's waiting room for your AI stack — nobody gets past the desk without Telegram verification.

Self-hosted Ollama behind a Docker internal network, accessed via Telegram Mini App. No inbound ports. No shared secrets in client code. Cryptographically verified, LAN-direct.

---

## How it works

```
[Telegram Servers] ←── long-poll (outbound only) ──── [telegram-bot]

[Your Phone / LAN Device]
    └─ opens Mini App (hosted on Cloudflare Pages / Vercel)
    └─ JS sends fetch → https://YOUR_LAN_IP:8443/api/chat
              ↓
         [nginx gateway]   (internal Docker network + published LAN port)
              ├─ auth_request → [auth-validator]  ← verifies Telegram HMAC initData
              └─ proxy_pass  → [ollama]           ← LLM inference, no internet access
```

**Key design decisions:**

| Instead of... | Openclaw uses... |
|---|---|
| Hardcoded bearer token in JS | Telegram's HMAC-signed `initData` — verified server-side, rotates per session |
| HTTP to local gateway | Self-signed TLS cert (auto-generated with LAN IP as SAN) |
| All services on one network | `internal_net: internal: true` — Ollama/auth have zero internet routing |
| Bot seeing backend services | `telegram-bot` is on a separate network — can reach Telegram, not your stack |

---

## Stack

| Service | Image / Build | Role |
|---|---|---|
| `nginx` | custom (nginx:alpine) | TLS gateway, static Mini App host, `auth_request` router |
| `auth-validator` | custom (python:3.12-slim) | Telegram `initData` HMAC verification |
| `telegram-bot` | custom (python:3.12-slim) | Long-poll bot, sends Mini App button to authorized users |
| `ollama` | `ollama/ollama:latest` | LLM inference backend |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | Optional browser UI (auth-gated at `/webui/`) |

---

## Prerequisites

- Docker + Docker Compose (or Docker Swarm for multi-node)
- A Telegram bot token from [@BotFather](https://t.me/botfather)
- Your Telegram user ID (get it from [@userinfobot](https://t.me/userinfobot))
- A free static host for the Mini App HTML (Cloudflare Pages, Vercel, GitHub Pages)
- NVIDIA GPU optional (required for GPU-accelerated Ollama)

---

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/hammerhead3377/waitingrm.git
cd waitingrm
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=your_bot_token_from_botfather
ALLOWED_USER_IDS=123456789          # your Telegram user ID
MINI_APP_URL=https://your-app.pages.dev
LAN_IP=192.168.1.100                # this machine's LAN IP
```

### 2. Deploy the Mini App HTML

Upload `nginx/www/index.html` to Cloudflare Pages, Vercel, or GitHub Pages.

Then edit one line in the uploaded `index.html`:
```js
const GATEWAY = "https://192.168.1.100:8443";   // your LAN_IP
```

Set this as your bot's Mini App URL in [@BotFather](https://t.me/botfather) → `/newapp` or `/myapps`.

### 3. Start the stack

```bash
docker compose up --build
```

On first boot, Nginx generates a self-signed TLS cert for your LAN IP. Accept it once in your browser at `https://LAN_IP:8443` before opening the Mini App (Telegram's WebView will otherwise silently fail the HTTPS connection).

### 4. Load a model

```bash
docker exec -it openclaw-ollama-1 ollama pull llama3
```

### 5. Open the bot

Send `/start` to your bot in Telegram → tap **Open Openclaw Terminal**.

---

## Docker Swarm (multi-node)

```bash
docker swarm init

# Create isolated overlay network
docker network create --driver overlay --internal internal_net

# Deploy
docker stack deploy -c docker-compose.yml openclaw
```

Change `internal_net.driver` to `overlay` in `docker-compose.yml` before deploying.

---

## Security notes

- **`initData` expiry:** auth-validator rejects tokens older than 24 hours (replay protection).
- **Network isolation:** `internal_net` has `internal: true` — no container on it can make outbound internet calls.
- **`telegram-bot` isolation:** the bot has no `networks:` clause, placing it on Docker's default bridge. It can reach Telegram but cannot see Ollama, auth-validator, or Open WebUI.
- **TLS:** self-signed cert covers your LAN IP. For a trusted cert, point a domain at your LAN IP and use Certbot with DNS challenge.
- **`ALLOWED_USER_IDS`:** gate is enforced in both the bot (UX) and auth-validator (cryptographic). Removing it from the bot does not bypass the validator.

---

## Acknowledgements

Concept and architecture by **Thomas**.
Implementation co-developed with [Claude](https://claude.ai) (Anthropic).

---

## License

MIT — fork freely, build something.
