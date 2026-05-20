# Multi-Model Intelligent Routing System for Hermes Agent
## ======================

This is a complete multi-model routing system designed for Hermes Agent, integrating:
- **Google AI Studio** (Free Tier with rate limiting)
- **DeepSeek** (Standard plan)
- **Qiniu Cloud / Volcengine Ark** (3M tokens monthly limit)
- **GLM / Z.AI** (2M tokens free tier + 6M for GLM-4.5-air)

## 🚀 Quick Start

### 1️⃣ Setup API Keys
```bash
cd D:/workspace/agentworkspace/Aagent
# Edit .env with your actual keys:
# - GOOGLE_AI_STUDIO_API_KEY (paste from Google AI Studio)
# - DEEPSEEK_API_KEY (from DeepSeek dashboard)
# - QINIU_API_KEY (Volcengine Ark console)
# - GLM_API_KEY (Z.AI or Zhipu API)
```

### 2️⃣ Test the Router
```bash
cd D:/workspace/agentworkspace/Aagent
python model_router.py
```

Expected output:
```
def fibonacci(n):              → Task: code          → Model: DEEPSEEK-CODER-V2 (priority=60)
请写一首诗                     → Task: creative      → Model: GOOGLE-AI-STUDIO   (priority=50)
计算积分：∫x²dx               → Task: analysis       → Model: GLM-4-EDGE        (priority=70)
```

### 3️⃣ Integrate with Hermes Agent
Add to your `~/.hermes/config.yaml`:
```yaml
custom_providers:
  - name: google-ai-studio
    base_url: "https://generativelanguage.googleapis.com/v1beta/models"
    api_key_env: GOOGLE_AI_STUDIO_API_KEY
    default_model: "gemini-2.0-flash-exp"
    cost_per_million_tokens: 0.0

  - name: deepseek-coder-v2
    base_url: "https://api.deepseek.com/v1/chat/completions"
    api_key_env: DEEPSEEK_API_KEY
    default_model: "deepseek-coder-v2.5"
    cost_per_million_tokens: 0.15

  - name: qiniu-ark-pro
    base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    api_key_env: QINIU_API_KEY
    default_model: "qwq-plus-latest"
    cost_per_million_tokens: 0.25

  - name: glm-4-edge
    base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    api_key_env: GLM_API_KEY
    default_model: "glm-4.6v"
    cost_per_million_tokens: 0.35
```

## 🧠 Task Classification

The router automatically classifies tasks:
| Task Type | Example Queries | Default Model |
|-----------|-----------------|---------------|
| **code** | `def `, `function`, `git commit` | DeepSeek-Coder-V2 |
| **creative** | `write story`, `poem`, `email draft` | Google AI Studio (free) |
| **analysis** | `pandas`, `numpy`, `plot graph` | GLM-4-Edge |
| **math** | `integral`, `solve equation`, `prove theorem` | Google AI Studio |
| **translation** | `translate to/from` | GLM-4-Edge |

## 🛡️ Rate Limit Protection (Google Free Tier)

The `rate_limit_monitor.py` script handles:
- ✅ 1500 requests/day tracking
- ✅ 60 requests/minute enforcement
- ✅ ~$20 credit limit monitoring
- ✅ Graceful fallback when limits hit

**Example of rate limiting in action:**
```
Request #15 | Status: OK ... (today: 14/1500)
Request #16 | Status: Rate limited: 15/60 req/min. Wait ~9s ...
⚠️  Google AI Studio rate limited, trying fallback...
```

## 🔄 Graceful Degradation Strategy

When the primary model fails:
1. Try next highest-priority model (same provider or different)
2. Switch to smaller parameter count models within same API
3. Fall back to OpenRouter with Claude-3.5-Sonnet (high cost but best quality)
4. Use local Ollama models if configured

## 📊 Cost Optimization

| Task Type | Default Model | Cost/1M tokens |
|-----------|--------------|----------------|
| Code | DeepSeek-Coder-V2 | ~$0.10-0.20 |
| Creative | Google AI Studio (free tier) | $0 (within limit) |
| Analysis | GLM-4-Edge | ~$0.50 |
| Math | Google AI Studio | $0 (within limit) |

**Set `cost_cap_per_minute: "$0.10"`** to automatically drop to cheaper models when costs exceed this threshold.

## 🛠️ Advanced Configuration

### Custom Task Patterns
Edit `model_router.py` → add new classification rules:
```python
code_patterns = [
    r'\bdef\s+\w+',        # Python function definition
    r'class\s+\w+',         # Class definitions  
    r'git commit',          # Git commands
]
```

### Multi-Key Redundancy (Optional)
For critical production use, configure credential pooling in `config.yaml`:
```yaml
credential_pool_strategies:
  rotate_on_error: true      # Try next API key on failure
  min_keys_per_provider: 2   # Keep at least 2 keys active
```

### Cron Integration (Google Rate Limit)
Schedule the rate limit monitor to log usage every 5 minutes:
```bash
cd D:/workspace/agentworkspace/Aagent
python rate_limit_monitor.py >> ~/.hermes/google_rate_limit.log 2>&1
```

## 📁 Project Structure

```
Aagent/
├── config.yaml              # Main routing configuration
├── .env                     # API keys (never commit this!)
├── model_router.py          # Core task classification & routing logic
├── rate_limit_monitor.py    # Google AI Studio rate limit handling
├── references/              # Documentation and troubleshooting guides
│   ├── 02-model-routing.md
│   └── troubleshooting-guide.md
├── templates/
│   └── model-config.yaml.example
└── scripts/
    └── test_router.py       # Standalone router tester
```

## 🧪 Testing

### Test the router without API calls:
```bash
cd D:/workspace/agentworkspace/Aagent
python -c "from model_router import MultiModelRouter; r = MultiModelRouter(); print(r.classify_task('def hello():'))"
def hello():              → Task: code          → Model: deepseek-coder-v2 (priority=60)
```

### Test rate limit monitoring:
```bash
cd D:/workspace/agentworkspace/Aagent
python rate_limit_monitor.py
# Output shows simulated request tracking within limits
```

## ⚠️ Important Notes

1. **Google AI Studio Free Tier**: The 1500 requests/day is an estimate — always check the [official rate limit page](https://aistudio.google.com/rate-limit)
2. **Qiniu Cloud Limit**: 3M tokens total — monitor usage via their dashboard to avoid unexpected charges
3. **GLM Free Tier**: The 2M tokens expires on June 10, 2026 — plan accordingly for production use
4. **API Key Security**: Never commit `.env` files to version control. Use Hermes' `hermes auth add` command to manage keys securely.

## 🔍 Troubleshooting

### "No models provided" error
- Re-save `config.yaml` as UTF-8 without BOM (Windows Notepad often adds one)
- Check that API key environment variables are set correctly

### Rate limit errors (429, 529)
- The router automatically falls back to the next model in priority order
- Check logs at `~/.hermes/logs/google_rate_limit.log`

### Model returns slow responses (> 5s think time)
- Router triggers `scale_down` → uses smaller parameter count model from same provider
- Configured via: `model_router.auto_switch.on_think_time: scale_down`

## 🌐 Next Steps

1. **Add more providers**: Copy the pattern for any new API (e.g., Mistral, Anthropic)
2. **Customize task patterns**: Edit `code_patterns` / `creative_keywords` in `model_router.py`
3. **Set up monitoring dashboard**: Use the stats from `rate_limit_monitor.get_usage_stats()`
4. **Production deployment**: Consider using Hermes' `cronjob` tool to schedule rate limit checks

## 📚 References

- [Google AI Studio Rate Limits](https://aistudio.google.com/rate-limit)
- [DeepSeek API Documentation](https://platform.deepseek.com/api-docs/)
- [Volcengine Ark Models](https://ark.cn-beijing.volces.com/docs)
- [GLM/Z.AI API Guide](https://open.bigmodel.cn/dev/basic/all)

## ✨ Demo Output

When you run `python model_router.py`, you'll see:
```
============================================================
Multi-Model Intelligent Router - Demo
============================================================
Query: def fibonacci(n):... → Task: code          → Model: DEEPSEEK-CODER-V2 (priority=60)
Query: 请写一首诗...        → Task: creative      → Model: GOOGLE-AI-STUDIO   (priority=50)
Query: 计算积分：∫x²dx...   → Task: analysis       → Model: GLM-4-EDGE        (priority=70)
============================================================
Router initialized successfully!
Configured providers: ['google-ai-studio', 'deepseek-coder-v2', ...
```

This is your complete multi-model routing system! 🚀