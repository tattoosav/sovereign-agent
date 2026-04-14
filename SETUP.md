# Sovereign Agent — Setup Guide

Step-by-step instructions for running locally, on Telegram, and as a hosted API.

---

## Prerequisites

- **Python 3.11+**
- **Git**
- **uv** (Python package manager) — install: `curl -LsSf https://astral.sh/uv/install.sh | sh`

For local LLM:
- **Ollama** — install: `curl -fsSL https://ollama.com/install.sh | sh`
- **GPU with 8+ GB VRAM** (or CPU-only with reduced performance)

---

## Step 1: Clone and Install

```bash
git clone https://github.com/tattoosav/sovereign-agent.git
cd sovereign-agent
uv sync
```

---

## Step 2: Choose Your LLM Backend

### Option A: Local with Ollama (free, private)

```bash
# Start Ollama
ollama serve

# Pull a model (pick one based on your VRAM):
ollama pull qwen2.5-coder:7b     # 8 GB VRAM — fast, basic
ollama pull qwen2.5-coder:14b    # 12 GB VRAM — good balance
ollama pull qwen2.5-coder:32b    # 24 GB VRAM — best local quality
```

Create `config.yaml`:
```yaml
llm:
  provider: "ollama"
  model: "qwen2.5-coder:14b"     # match what you pulled
  base_url: "http://localhost:11434"
  max_tokens: 16384
  context_window: 32768           # lower to 16384 if low on RAM

  models:
    small: "qwen2.5-coder:7b"    # only if you pulled multiple
    medium: "qwen2.5-coder:14b"
    large: "qwen2.5-coder:14b"   # set all to same if you only have one
```

### Option B: Cloud API (no GPU needed)

Pick a provider — all are OpenAI-compatible:

| Provider | Signup | Cheapest Coding Model |
|---|---|---|
| Together.ai | together.ai | Qwen/Qwen2.5-Coder-32B-Instruct |
| Groq | groq.com | llama-3.3-70b-versatile |
| OpenRouter | openrouter.ai | many options |
| OpenAI | platform.openai.com | gpt-4o-mini |

Create `config.yaml`:
```yaml
llm:
  provider: "openai"
  model: "Qwen/Qwen2.5-Coder-32B-Instruct"  # or whatever model
  base_url: "https://api.together.xyz/v1"      # your provider's URL
  api_key: "your-api-key-here"
  max_tokens: 16384
  context_window: 32768
```

---

## Step 3: Test the CLI

```bash
# Quick test (v2 agent with intelligence features)
uv run python -m src.main_v2
```

You should see:
```
╔═══════════════════════════════════════════════════════════════╗
║              SOVEREIGN AGENT v2                               ║
╚═══════════════════════════════════════════════════════════════╝

✓ Connected to Ollama
✓ Dynamic routing enabled (7B/14B/32B)
✓ RAG context retrieval enabled

You: hello, what can you do?
```

Type `exit` to quit. If this works, your LLM backend is configured correctly.

---

## Step 4: Start the Web Server

```bash
# For local development (no auth required):
SOVEREIGN_AUTH_DISABLED=1 uv run python -m src.web

# For production (auth enabled):
uv run python -m src.web
```

On first startup with auth enabled, it prints:
```
Default API key: sk-a1b2c3d4e5f6...
Save this — it won't be shown again.
```

**Save that key.** It's your admin key for managing everything.

Open http://localhost:8000 in your browser to use the web chat UI.

### Test the API

```bash
# Health check (no auth needed)
curl http://localhost:8000/health

# Chat (needs auth unless SOVEREIGN_AUTH_DISABLED=1)
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer sk-your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "write a python function to reverse a string"}'
```

---

## Step 5: Set Up the Telegram Bot

### 5a: Create a bot with @BotFather

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My Coding Agent")
4. Choose a username (e.g., "my_coding_agent_bot")
5. BotFather gives you a token like `7123456789:AAH...`

### 5b: Get your Telegram user ID

1. Search for **@userinfobot** on Telegram
2. Send it any message
3. It replies with your user ID (a number like `123456789`)

### 5c: Run the bot

The web server must be running first (Step 4). Then in a second terminal:

```bash
TELEGRAM_BOT_TOKEN="7123456789:AAHxxx..."  \
SOVEREIGN_API_KEY="sk-your-admin-key"       \
SOVEREIGN_BASE_URL="http://localhost:8000"  \
TELEGRAM_ALLOWED_USERS="123456789"          \
uv run python -m src.integrations.telegram_bot
```

You should see:
```
Bot running: @my_coding_agent_bot
```

Now open Telegram, find your bot, and send `/start`.

---

## Step 6: Create API Keys for Clients

With your admin key, create keys for other users:

```bash
# Create a key with custom limits
curl -X POST http://localhost:8000/admin/keys \
  -H "Authorization: Bearer sk-your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "client-alice", "rate_limit": 20, "daily_limit": 500}'

# Response:
# {"key": "sk-new-client-key...", "name": "client-alice", "message": "Store safely..."}
```

```bash
# List all keys
curl http://localhost:8000/admin/keys \
  -H "Authorization: Bearer sk-your-admin-key"

# Check usage for a specific key (use the hash prefix from list)
curl http://localhost:8000/admin/usage/a1b2c3d4e5f6?hours=24 \
  -H "Authorization: Bearer sk-your-admin-key"
```

---

## Step 7: Deploy to a Server (for public access)

### Option A: VPS + Cloud LLM (cheapest, simplest)

1. Get a VPS ($4-10/mo): Hetzner, DigitalOcean, or Vultr
2. Install Python 3.11+, uv, and git on the VPS
3. Clone the repo and `uv sync`
4. Set `config.yaml` with a cloud LLM provider (Step 2 Option B)
5. Run with a process manager:

```bash
# Install process manager
pip install supervisor

# Or use systemd (create /etc/systemd/system/sovereign-agent.service):
[Unit]
Description=Sovereign Agent API
After=network.target

[Service]
Type=simple
User=sovereign
WorkingDirectory=/opt/sovereign-agent
ExecStart=/opt/sovereign-agent/.venv/bin/python -m src.web --host 0.0.0.0 --port 8000
Restart=always
Environment=SOVEREIGN_CORS_ORIGINS=https://yourdomain.com

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable sovereign-agent
sudo systemctl start sovereign-agent
```

6. Put nginx or Caddy in front for HTTPS:

```
# /etc/caddy/Caddyfile
yourdomain.com {
    reverse_proxy localhost:8000
}
```

### Option B: Your PC + Cloudflare Tunnel (free hosting, use your GPU)

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Expose your local server
cloudflared tunnel --url http://localhost:8000
```

This gives you a public URL like `https://random-name.trycloudflare.com` — use it as the Telegram bot's `SOVEREIGN_BASE_URL`.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_AUTH_DISABLED` | `""` | Set to `1` to disable auth (local dev only) |
| `SOVEREIGN_CORS_ORIGINS` | `http://localhost:8000,...` | Comma-separated allowed origins |
| `SOVEREIGN_MODEL` | from config.yaml | Override default model |
| `SOVEREIGN_BASE_URL` | from config.yaml | Override LLM API URL |
| `SOVEREIGN_API_KEY` | from config.yaml | Override LLM API key |
| `SOVEREIGN_CONTEXT_WINDOW` | `32768` | Override context window size |
| `SOVEREIGN_MAX_TOKENS` | `16384` | Override max generation tokens |
| `SOVEREIGN_LOG_LEVEL` | `INFO` | Logging verbosity |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `TELEGRAM_ALLOWED_USERS` | `""` | Comma-separated Telegram user IDs |

---

## Troubleshooting

**"Cannot connect to Ollama server"**
- Run `ollama serve` in another terminal
- Check that `base_url` in config.yaml matches (default: `http://localhost:11434`)

**"Model not found"**
- Run `ollama list` to see installed models
- Pull the model: `ollama pull qwen2.5-coder:14b`
- Make sure model name in `config.yaml` exactly matches `ollama list` output

**"Rate limit exceeded"**
- Wait 60 seconds, or increase the key's `rate_limit` via admin endpoint

**Telegram bot not responding**
- Check that the web server is running
- Verify `SOVEREIGN_BASE_URL` is reachable from where the bot runs
- Check `TELEGRAM_ALLOWED_USERS` includes your user ID
- Look at bot terminal output for errors

**Out of memory (Ollama)**
- Use a smaller model or lower quantization
- Reduce `context_window` in config.yaml (try `16384`)
- Close other GPU-using applications
