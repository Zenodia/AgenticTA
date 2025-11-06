# LLM Module

Scalable, provider-agnostic LLM interface for AgenticTA.

## Quick Example

```python
from llm import LLMClient

llm = LLMClient()

# Make a call
response = await llm.call(
    prompt="Generate chapter titles...",
    use_case="chapter_title_generation"
)

# Stream response
async for chunk in llm.stream(
    prompt="Create study material...",
    use_case="study_material_generation"
):
    print(chunk, end="", flush=True)
```

---

## Architecture

```
llm/
├── client.py             # LLMClient - main interface
├── config.py             # Configuration loader (includes load_dotenv)
├── factory.py            # Handler factory
├── handlers.py           # Use case handlers
└── providers/            # Provider implementations
    ├── base.py          # Abstract base class
    ├── nvidia.py        # NVIDIA provider
    └── astra.py         # ASTRA provider
```

---

## Configuration

All settings in `llm_config.yaml`:

```yaml
providers:
  nvidia:
    type: nvidia
    api_key_env: NVIDIA_API_KEY
    models:
      fast: openai/gpt-oss-120b
      powerful: meta/llama-3.1-405b-instruct

use_cases:
  chapter_title_generation:
    provider: nvidia
    model: fast
    max_tokens: 1024
    temperature: 0.7
```

**No code changes needed** - just edit YAML and restart!

---

## Active Providers

### NVIDIA
- **API Key**: `NVIDIA_API_KEY` environment variable
- **Models**: `fast`, `powerful`, `reasoning`

### ASTRA (Optional)
- **API Key**: `ASTRA_TOKEN` environment variable
- **Models**: `nvidia/llama-3.3-nemotron-super-49b-v1`

### Inactive Providers
OpenAI and Anthropic are implemented but commented out in config.

---

## Use Cases

Configure any LLM task in `llm_config.yaml`:

```yaml
use_cases:
  my_feature:
    type: llm
    provider: nvidia
    model: fast
    max_tokens: 2048
    temperature: 0.7
```

Then use it:

```python
result = await llm.call(
    prompt="...",
    use_case="my_feature",
    max_tokens=4096  # Override if needed
)
```

---

## Adding Custom Providers

### 1. Create Provider Class

```python
# llm/providers/myprovider.py
from .base import LLMProvider

class MyProvider(LLMProvider):
    async def call(self, messages, max_tokens, temperature, **kwargs):
        # Your API call here
        pass
    
    async def stream(self, messages, max_tokens, temperature, **kwargs):
        # Streaming implementation
        pass
```

### 2. Register Provider

```python
# llm/providers/__init__.py
from .myprovider import MyProvider

PROVIDER_REGISTRY = {
    "nvidia": NvidiaProvider,
    "astra": AstraProvider,
    "myprovider": MyProvider,  # Add here
}
```

### 3. Add to Config

```yaml
providers:
  myprovider:
    type: myprovider
    api_key_env: MY_API_KEY
    models:
      default: my-model

use_cases:
  my_feature:
    provider: myprovider
    model: default
```

---

## Environment Variables

```bash
# Required
export NVIDIA_API_KEY=nvapi-xxx...

# Optional
export ASTRA_TOKEN=xxx...

# Override specific use case provider
export LLM_CHAPTER_TITLE_GENERATION_PROVIDER=astra

# Override default provider
export LLM_DEFAULT_PROVIDER=nvidia
```

**Note**: `load_dotenv()` is called automatically in `config.py`

---

## Testing

```bash
# In Docker container
make test

# Or manually
docker exec agenticta python -c "
from llm import LLMClient
from llm.config import load_config
print('✅ LLM module OK')
c = load_config()
print(f'✅ Config: {len(c[\"providers\"])} providers, {len(c[\"use_cases\"])} use cases')
"
```

---

## Troubleshooting

### "Module 'openai' not found"
```bash
pip install openai aiohttp pyyaml python-dotenv
```

### "Unknown provider"
Check `llm_config.yaml` and `llm/providers/__init__.py` match.

### "API key not found"
```bash
# Check environment
docker exec agenticta env | grep API_KEY

# Ensure .env file exists
cat .env
```

### "Unknown use case"
Add to `llm_config.yaml` or check spelling.

---

## Dependencies

```
openai>=1.0.0           # For NVIDIA provider
aiohttp>=3.8.0          # For ASTRA provider
pyyaml>=6.0             # For config
python-dotenv>=0.19.0   # For .env files
```

---

## Future Enhancements

- [ ] Retry middleware with exponential backoff
- [ ] Response caching (Redis/memory)
- [ ] Token counting and cost tracking
- [ ] Metrics and logging (Prometheus)
- [ ] A/B testing framework
- [ ] Prompt versioning
