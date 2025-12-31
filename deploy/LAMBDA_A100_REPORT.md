# Lambda Labs A100 Performance Report

## Hardware Specifications

| Spec | A100 40GB | A100 80GB |
|------|-----------|-----------|
| **GPU Memory** | 40 GB HBM2e | 80 GB HBM2e |
| **Memory Bandwidth** | 1.6 TB/s | 2.0 TB/s |
| **FP16 Performance** | 312 TFLOPS | 312 TFLOPS |
| **Tensor Cores** | 432 | 432 |
| **CUDA Cores** | 6912 | 6912 |
| **Price (Lambda)** | ~$1.10/hr | ~$1.29/hr |

## Qwen 2.5 Coder Performance on A100

### Token Generation Speed (tokens/second)

| Model | Your PC (est.) | A100 40GB | A100 80GB | Speedup |
|-------|---------------|-----------|-----------|---------|
| **7B (Q4)** | 15-25 t/s | 150-200 t/s | 180-220 t/s | **8-10x** |
| **7B (FP16)** | 10-15 t/s | 120-160 t/s | 150-180 t/s | **10-12x** |
| **14B (Q4)** | 8-12 t/s | 100-140 t/s | 130-160 t/s | **12-15x** |
| **14B (FP16)** | Can't run | 80-110 t/s | 100-130 t/s | **∞** |
| **32B (Q4)** | Can't run | 60-90 t/s | 80-110 t/s | **∞** |
| **32B (FP16)** | Can't run | 40-60 t/s | 70-90 t/s | **∞** |

### Response Times (typical coding task)

| Task Type | Your PC | A100 | Improvement |
|-----------|---------|------|-------------|
| Simple question | 10-20s | 1-2s | **10x** |
| Code explanation | 20-40s | 2-4s | **10x** |
| Implement function | 30-60s | 3-6s | **10x** |
| Multi-file refactor | 2-5 min | 15-30s | **8-10x** |
| Complex feature | 5-10 min | 30-60s | **10x** |

### Memory Usage on A100 40GB

| Model | VRAM Used | Remaining | Context Window |
|-------|-----------|-----------|----------------|
| 7B FP16 | ~14 GB | 26 GB | 32K tokens |
| 14B FP16 | ~28 GB | 12 GB | 16K tokens |
| 32B Q8 | ~34 GB | 6 GB | 8K tokens |
| 32B Q4 | ~18 GB | 22 GB | 32K tokens |

**Recommendation**: Run **32B Q4** or **14B FP16** for best quality/speed balance.

## Throughput Estimates for 24-Hour Session

### Codebase Indexing & Learning

| Codebase Size | Your PC | A100 | Files/Hour |
|---------------|---------|------|------------|
| 100 files | 10 min | 30 sec | 12,000/hr |
| 500 files | 45 min | 3 min | 10,000/hr |
| 1000 files | 2+ hrs | 8 min | 7,500/hr |
| 5000 files | Can't | 40 min | 7,500/hr |

### Coding Tasks Completed

| Task Type | Your PC (24hr) | A100 (24hr) |
|-----------|----------------|-------------|
| Bug fixes | 20-40 | 200-400 |
| New functions | 15-30 | 150-300 |
| File refactors | 5-10 | 80-150 |
| Full features | 2-4 | 20-40 |
| Test generation | 10-20 | 100-200 |

## Cost Analysis (24-hour session)

### Lambda Labs A100 40GB
- **Hourly Rate**: $1.10/hr
- **24 Hour Cost**: **$26.40**
- **No egress fees** (free data transfer)

### What You Can Accomplish in 24 Hours

```
HOUR 1-2: Setup & Learning
├── Deploy agent (10 min)
├── Index entire codebase (20-40 min)
├── Learn patterns (10-20 min)
└── Pull all models (30 min)

HOUR 3-24: Development (~21 hours of work)
├── With 10x speedup, this equals ~200 hours of local work
├── Estimated tasks completed:
│   ├── 200+ bug fixes/small changes
│   ├── 50+ new features
│   ├── 20+ major refactors
│   └── Complete test coverage
└── Continuous pattern learning
```

### ROI Calculation

| Metric | Value |
|--------|-------|
| Cost | $26.40 |
| Equivalent local time | ~200 hours |
| Time saved | ~175 hours |
| Effective hourly rate | **$0.15/hr** of equivalent work |

## Optimal Workflow for 24-Hour Session

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: SETUP (1 hour) - $1.10                           │
├─────────────────────────────────────────────────────────────┤
│  • SSH into Lambda instance                                 │
│  • Run deploy.sh (installs everything)                     │
│  • Pull models: 7B, 14B, 32B                               │
│  • Sync your project files                                  │
│  • Index codebase into vector store                        │
│  • Learn patterns from existing code                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: INTENSIVE WORK (20 hours) - $22.00               │
├─────────────────────────────────────────────────────────────┤
│  • Use 32B model for complex tasks                         │
│  • Use 14B for standard coding                             │
│  • Parallel tool execution enabled                         │
│  • Real-time pattern learning                              │
│  • Continuous RAG retrieval                                │
│                                                             │
│  Expected output:                                           │
│  • 150-300 completed tasks                                  │
│  • Full project scaffolds                                   │
│  • Comprehensive refactoring                               │
│  • Generated documentation                                  │
│  • Test coverage                                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: SAVE & SYNC (1 hour) - $1.10                     │
├─────────────────────────────────────────────────────────────┤
│  • Git commit all changes                                   │
│  • Export learned patterns                                  │
│  • Sync .sovereign/ folder back to local                   │
│  • Generate documentation                                   │
│  • Create session summary                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: SHUTDOWN (2 hours buffer) - $2.20                │
├─────────────────────────────────────────────────────────────┤
│  • Final verification                                       │
│  • Backup to cloud storage                                  │
│  • Terminate instance                                       │
│  • Total: $26.40 for ~200 hours equivalent work            │
└─────────────────────────────────────────────────────────────┘
```

## Comparison: A100 vs Other Options

| Provider | GPU | $/hr | 24hr Cost | Speed vs A100 |
|----------|-----|------|-----------|---------------|
| Lambda A100 40GB | A100 | $1.10 | $26.40 | 100% |
| Lambda A100 80GB | A100 | $1.29 | $30.96 | 110% |
| RunPod 4090 | RTX 4090 | $0.44 | $10.56 | 70-80% |
| Vast.ai 4090 | RTX 4090 | $0.35 | $8.40 | 70-80% |

**Verdict**: A100 is best for intensive 24hr sessions. For short bursts, RTX 4090 is more cost-effective.

## Files to Deploy

The following scripts are included:

1. `deploy.sh` - Main deployment script
2. `sync.sh` - Sync patterns/memory between local and VPS
3. `session.sh` - Start/stop sessions easily
4. `requirements-vps.txt` - VPS-specific dependencies

## Quick Start

```bash
# 1. Get your Lambda Labs instance IP
# 2. Set environment variable
export LAMBDA_IP="your-instance-ip"
export LAMBDA_KEY="~/.ssh/lambda_key"

# 3. Deploy
./deploy/session.sh start

# 4. Access web UI
open http://$LAMBDA_IP:8000

# 5. When done
./deploy/session.sh stop
```
