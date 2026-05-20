# Multi-Model Routing Troubleshooting Guide
## ======================

This guide helps you diagnose and resolve common issues when using the multi-model routing system.

---

## 🔍 Common Issues & Solutions

### Issue 1: "No models provided" error on first run
**Symptoms:** Hermes returns "Error: No models provided in config"

**Root Cause:** Config file saved with UTF-8 BOM (Byte Order Mark) by Windows Notepad or other editors.

**Solution:**
```bash
# Option A: Re-save config.yaml without BOM using VSCode
# File → Save With Encoding → Unicode (UTF-8 without BOM)

# Option B: Use the Hermes CLI tool which writes without BOM:
hermes config edit  # This saves as UTF-8 without BOM automatically
```

**Alternative:** Manually remove the BOM by opening with hex editor and deleting first 3 bytes.

---

### Issue 2: Rate limit errors (429, 529) from Google AI Studio
**Symptoms:** Responses fail with "Too many requests" or "Overload" errors

**Root Cause:** Google's free tier has a hard limit of ~60 requests/minute. The rate_limit_monitor.py script tracks this.

**Solutions (in order of preference):**
1. **Wait and retry** - The router auto-falls back to the next model after 5-10 seconds:
   ```bash
   # Example fallback log:
   ⚠️  Google AI Studio rate limited, trying fallback...
   Using DEEPSEEK-CODER-V2 instead (priority=60)
   ```

2. **Increase the per-minute limit** in `rate_limit_monitor.py` if you have a paid Google account:
   ```python
   self.max_requests_per_minute = 180  # Paid tier allows higher limits
   ```

3. **Disable Google for certain task types** - Edit `config.yaml` to remove Google from specific routes:
   ```yaml
   creative_writing:                    
     preferred_model: "qiniu-ark-pro"  # Skip Google entirely
     fallback_to: ["deepseek-coder-v2"]
   ```

---

### Issue 3: API key authentication failures (401, 403)
**Symptoms:** Model returns "Invalid API key" or "Access denied"

**Root Cause:** One of three possibilities:
- The `.env` file is not being loaded correctly
- The API key has been revoked/expired in the provider's dashboard
- The base URL for the model is incorrect

**Solutions:**
1. **Verify .env loading:** Add this debug print to your script:
   ```python
   import os
   print(f"GOOGLE_AI_STUDIO_API_KEY exists: {os.getenv('GOOGLE_AI_STUDIO_API_KEY')}")
   # Should show: "exists: True" with actual key (or '****' if redacted)
   ```

2. **Check the API key's status** - Visit each provider's dashboard:
   - Google AI Studio: https://aistudio.google.com/app/apikey  
   - DeepSeek: https://platform.deepseek.com/account/overview  
   - Volcengine Ark: https://ark.cn-beijing.volces.com/console  
   - GLM/Z.AI: https://open.bigmodel.cn/usercenter/apicount

3. **Verify base URL** for each model in `config.yaml`:
   ```yaml
   google-ai-studio:
     base_url: "https://generativelanguage.googleapis.com/v1beta/models"  # ✓ Correct
     
   deepseek-coder-v2:
     base_url: "https://api.deepseek.com/v1/chat/completions"  # ✓ Correct
     
   qiniu-ark-pro:
     base_url: "https://ark.cn-beijing.volces.com/api/v3/chat/completions"  # ✓ Correct
     
   glm-4-edge:
     base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # ✓ Correct
   ```

---

### Issue 4: Model returns very slow responses (> 5s think time)
**Symptoms:** Response takes more than expected, often with partial or repetitive outputs

**Root Cause:** The model is overloaded (common for free-tier APIs) or the temperature setting is too high.

**Solutions:**
1. **Let the router trigger auto-downgrade** - Configured in `config.yaml`:
   ```yaml
   model_router:
     auto_switch:
       on_think_time: scale_down  # Automatically use smaller models after >4s
       latency_threshold_ms: 4000
   graceful_degradation:
     max_latency_ms: 5000         # Auto-downgrade after 5s think time
     cost_cap_per_minute: "$0.10" # Drop to cheaper models beyond this threshold
   ```

2. **Manually configure smaller models** - Add model-specific config for each provider:
   ```yaml
   google-ai-studio:
     default_model: "gemini-2.0-flash-exp"  # Smaller, faster than gemini-pro
     fallback_models: ["gemini-1.5-flash", "gemini-pro"]
   
   qiniu-ark-pro:
     default_model: "qwq-plus-latest"        # Already a smaller model
     fallback_models: ["deepseek-v3", "qwen2.5"]
   ```

3. **Increase the latency threshold** if you have slower network connections:
   ```yaml
   graceful_degradation:
     max_latency_ms: 10000  # Wait longer before downgrading (default is 5s)
   ```

---

### Issue 5: Task classification is wrong or inconsistent
**Symptoms:** The same query gets classified differently on repeated runs, or tasks are misrouted

**Root Cause:** Classification patterns may not cover all cases, or regex matching has edge cases.

**Solutions:**
1. **Add custom patterns** to `model_router.py`:
   ```python
   # Example: Detect Chinese programming queries
   code_patterns.extend([
       r'用\s+[a-z]+\s+画|绘制',  # "use python to draw"
       r'写一个\s*[脚本程序]',      # "write a script"
   ])
   
   # Example: Detect LaTeX-style math in Markdown
   math_patterns.extend([
       r'\$.*\$',                 # Inline LaTeX: $E=mc^2$
       r'\\begin',               # Display math blocks
   ])
   ```

2. **Inspect classification output** to debug:
   ```python
   from model_router import MultiModelRouter
   router = MultiModelRouter()
   
   query = "请帮我写一个爬虫脚本"
   print(f"Query: {query}")
   task_type, priority_model = router.get_best_model(router.classify_task(query))
   print(f"Classified as: {task_type} → Using: {priority_model}")
   ```

3. **Create a whitelist of known-good queries** for testing:
   ```python
   KNOWN_QUERIES = {
       "def hello():": ("code_generation", "deepseek-coder-v2"),
       "写一首诗": ("creative_writing", "google-ai-studio"),
       "画一个图表": ("data_analysis", "glm-4-edge"),
   }
   
   def classify_with_cache(self, user_query: str) -> tuple[str, str]:
       if user_query in KNOWN_QUERIES:
           return KNOWN_QUERIES[user_query]
       # Fall back to normal classification
       ...
   ```

---

### Issue 6: API key quota exhausted (daily/total limits)
**Symptoms:** Requests are rejected with "Quota exceeded" or similar messages

**Root Cause:** Provider's free tier has hard caps that cannot be extended without upgrading.

**Solutions:**
1. **Monitor usage before hitting limits** - Add to your script:
   ```python
   from rate_limit_monitor import GoogleRateLimitMonitor
   monitor = GoogleRateLimitMonitor()
   
   if not monitor.check_rate_limit()[0]:  # First check returns (allowed, message)
       print(f"⚠️  {monitor.check_rate_limit()[1]}")
       return self.route_request(user_query, max_retries - 1)  # Try next model
   ```

2. **Set up usage alerts** using the monitor's stats:
   ```python
   stats = monitor.get_usage_stats()
   if stats['requests_today'] > (stats['daily_limit'] * 0.8):  # At 80% of limit
       print(f"⚠️  Using {100*(stats['requests_today']/stats['daily_limit']):.1f}% of daily quota")
   ```

3. **Prefer free-tier models for low-priority tasks** - Configure in `config.yaml`:
   ```yaml
   graceful_degradation:
     priority_models: ["google-ai-studio", "deepseek-coder-v2", "glm-4-edge"]  # Free first
     fallback_chain:
       - primary: "qiniu-ark-pro"      # Paid, use only for critical tasks
         secondary: "deepseek-coder-v2"
   ```

---

## 🧰 Diagnostic Commands

### Check current configuration
```bash
cd D:/workspace/agentworkspace/Aagent
python -c "from model_router import MultiModelRouter; r=MultiModelRouter(); print(r.providers.keys())"
# Should output: dict_keys(['google-ai-studio', 'deepseek-coder-v2', ...])
```

### Test rate limit monitoring (without making real requests)
```bash
cd D:/workspace/agentworkspace/Aagent
python -c "from rate_limit_monitor import GoogleRateLimitMonitor; m=GoogleRateLimitMonitor(); print(m.check_rate_limit())"
# Output: (True, 'OK: 0/60 req/min')
```

### Test task classification with various inputs
```bash
cd D:/workspace/agentworkspace/Aagent
python test_router.py
# Shows breakdown of all classification categories
```

---

## 🛠️ Advanced Debugging

### Enable verbose logging in model_router.py
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add to classify_task():
logger.debug(f"Classifying: {user_query!r} → Task: {task_type}")
```

### Monitor API usage in real-time
```python
from rate_limit_monitor import GoogleRateLimitMonitor
monitor = GoogleRateLimitMonitor()

# Simulate a request
allowed, message = monitor.check_rate_limit()
if allowed:
    monitor.record_request()  # Log the request
else:
    print(f"Blocked: {message}")
```

### Check environment variable loading
```bash
cd D:/workspace/agentworkspace/Aagent
python -c "import os; print([k for k in sorted(os.environ.keys()) if 'API_KEY' in k])"
# Should show all configured keys: ['DEEPSEEK_API_KEY', 'GLM_API_KEY', ...]
```

---

## 📞 Support Resources

- **Google AI Studio Rate Limit**: https://aistudio.google.com/rate-limit (official documentation)
- **DeepSeek API Docs**: https://platform.deepseek.com/api-docs/
- **Volcengine Ark Console**: https://ark.cn-beijing.volces.com/docs
- **GLM/Z.AI Docs**: https://open.bigmodel.cn/dev/basic/all

**For Hermes Agent-specific issues:**
- Report to: https://github.com/NousResearch/hermes-agent/issues  
- Check the main docs: https://hermes-agent.nousresearch.com/docs/

---

## 🎯 Best Practices (Learned from Experience)

1. **Always test your configuration with `test_router.py` first** before deploying to production
2. **Set up quota monitoring alerts** using the rate_limit_monitor module
3. **Prefer smaller models for free-tier APIs** - they're faster and more cost-effective
4. **Keep API keys rotated every 90 days** to prevent accidental exposure or revocation
5. **Use credential pooling** (`credential_pool_strategies`) for critical production workloads
6. **Document your model selection rationale** in the README so future maintainers understand why you chose each provider
