# Sovereign Agent - Lambda Labs Deployment

Deploy your Sovereign Agent to a Lambda Labs A100 GPU instance for 10x faster performance.

## Quick Start (5 minutes)

### 1. Rent a Lambda Labs Instance

1. Go to [Lambda Labs Cloud](https://cloud.lambdalabs.com/)
2. Launch an **A100 40GB** instance (~$1.10/hr)
3. Download your SSH key (save as `~/.ssh/lambda_key`)
4. Note your instance IP address

### 2. Configure

**Option A: Environment Variables (Recommended)**
```bash
# On Windows (PowerShell)
$env:LAMBDA_IP = "your-instance-ip"
$env:LAMBDA_KEY = "$HOME\.ssh\lambda_key"

# On Windows (Git Bash) / Linux / Mac
export LAMBDA_IP="your-instance-ip"
export LAMBDA_KEY="$HOME/.ssh/lambda_key"
```

**Option B: Create .env file**
```bash
# Create deploy/.env
echo "LAMBDA_IP=your-instance-ip" > deploy/.env
echo "LAMBDA_KEY=$HOME/.ssh/lambda_key" >> deploy/.env
```

### 3. Deploy & Start

```bash
# First time: Deploy the environment
ssh -i ~/.ssh/lambda_key ubuntu@$LAMBDA_IP 'bash -s' < deploy/deploy.sh

# Start a session
./deploy/session.sh start
```

### 4. Access Your Agent

Open in browser: `http://YOUR_IP:8000`

### 5. When Done

```bash
# Sync everything back and stop
./deploy/session.sh stop

# IMPORTANT: Stop your Lambda instance to stop billing!
```

---

## Scripts Reference

### `deploy.sh` - One-time Setup
Run this on the VPS to install everything:
- Ollama
- Python/uv
- Qwen models (7B, 14B, 32B)
- Creates data directories

```bash
# SSH in and run
ssh -i ~/.ssh/lambda_key ubuntu@$LAMBDA_IP
bash ~/sovereign-agent/deploy/deploy.sh
```

### `sync.sh` - Sync Files
Sync code and learned patterns between local and VPS:

```bash
./deploy/sync.sh push          # Push code + patterns to VPS
./deploy/sync.sh pull          # Pull code + patterns from VPS
./deploy/sync.sh push-code     # Push only code
./deploy/sync.sh push-patterns # Push only patterns
./deploy/sync.sh status        # Check VPS status
```

### `session.sh` - Manage Sessions
Easy session management:

```bash
./deploy/session.sh start      # Sync + start agent
./deploy/session.sh stop       # Stop + sync back
./deploy/session.sh status     # Show status
./deploy/session.sh logs       # Stream logs
./deploy/session.sh shell      # SSH into VPS
./deploy/session.sh learn      # Learn patterns from codebase
./deploy/session.sh index      # Index for RAG
```

---

## Workflow Examples

### Intensive 24-Hour Session

```bash
# 1. Start Lambda instance, note IP
export LAMBDA_IP=123.45.67.89

# 2. First-time setup (10 min)
ssh ubuntu@$LAMBDA_IP 'curl -fsSL https://ollama.com/install.sh | sh'
./deploy/sync.sh push
ssh ubuntu@$LAMBDA_IP 'cd ~/sovereign-agent && bash deploy/deploy.sh'

# 3. Start working
./deploy/session.sh start

# 4. Work for hours...
# Access http://123.45.67.89:8000

# 5. End session
./deploy/session.sh stop

# 6. STOP THE LAMBDA INSTANCE!
```

### Quick Development Session (2-3 hours)

```bash
# Start
export LAMBDA_IP=your-ip
./deploy/session.sh start

# Work...

# End
./deploy/session.sh stop
```

### Resume Existing Session

If you have a running instance from before:

```bash
export LAMBDA_IP=your-ip
./deploy/session.sh status  # Check if agent is running
./deploy/session.sh start   # Restart if needed
```

---

## Performance on A100

| Model | Speed | Best For |
|-------|-------|----------|
| qwen2.5-coder:7b | 150-200 t/s | Quick tasks |
| qwen2.5-coder:14b | 100-140 t/s | Standard coding |
| qwen2.5-coder:32b | 60-90 t/s | Complex tasks |

**Compared to local**: 8-10x faster response times.

---

## Troubleshooting

### Cannot connect to VPS
```bash
# Check SSH key permissions
chmod 600 ~/.ssh/lambda_key

# Test connection
ssh -i ~/.ssh/lambda_key ubuntu@$LAMBDA_IP echo "Connected"
```

### Agent won't start
```bash
# Check logs
./deploy/session.sh logs

# SSH in and check manually
./deploy/session.sh shell
cd ~/sovereign-agent
uv run python -m src.web --host 0.0.0.0
```

### Ollama not running
```bash
./deploy/session.sh shell
sudo systemctl start ollama
ollama list
```

### Port blocked
Lambda Labs uses port 8000 by default. If blocked:
```bash
# SSH tunnel
ssh -i ~/.ssh/lambda_key -L 8000:localhost:8000 ubuntu@$LAMBDA_IP
# Then access http://localhost:8000
```

---

## Cost Optimization

| Duration | Cost | Productivity |
|----------|------|--------------|
| 2 hours | $2.20 | ~20 hrs equivalent |
| 8 hours | $8.80 | ~80 hrs equivalent |
| 24 hours | $26.40 | ~200 hrs equivalent |

**Tips:**
- Stop instance when not actively using
- Use 7B model for simple tasks (faster, less VRAM)
- Batch your intensive work sessions
- Sync patterns back - they persist locally

---

## File Structure

```
deploy/
├── README.md              # This file
├── LAMBDA_A100_REPORT.md  # Detailed performance report
├── deploy.sh              # One-time VPS setup
├── sync.sh                # Sync files between local/VPS
├── session.sh             # Session management
└── .env                   # Your config (create this)
```

---

## Security Notes

- SSH keys stay on your machine
- Code runs on Lambda's isolated VMs
- Data synced via encrypted SSH/rsync
- No credentials stored on VPS
- Instance terminated = data gone (sync first!)
