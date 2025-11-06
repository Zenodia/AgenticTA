# AgenticTA Quickstart Guide

Get up and running with AgenticTA in minutes!

---

## 🚀 Quick Setup

### 1. Prerequisites
- Docker with GPU support
- NVIDIA API key

### 2. Environment Setup
```bash
# Create .env file with your API key
echo "NVIDIA_API_KEY=your_key_here" > .env

# Optional: Add ASTRA token for enhanced models
echo "ASTRA_TOKEN=your_token_here" >> .env
```

### 3. Start Services
```bash
# Start all services (RAG, Milvus, Redis, etc.)
make up

# Wait ~30 seconds for services to be ready, then start Gradio
make gradio
```

### 4. Open UI
Visit **http://localhost:7860** in your browser

---

## 📚 Usage

### Upload PDFs
1. Click "Upload PDF files" 
2. Select one or more PDFs
3. Click "Generate Curriculum"
4. Wait while AI analyzes your documents

### Study
- Browse generated chapters
- Click a chapter to view study materials
- Use the Study Buddy chat for questions

---

## 🛠️ Common Commands

```bash
# View all commands
make help

# Check service status
make status

# View logs
make logs              # AgenticTA logs
make logs-gradio       # Gradio UI logs
make logs-rag          # RAG server logs

# Restart services
make restart           # All services
make restart-gradio    # Just Gradio

# Enter container shell
make shell

# Stop everything
make down

# Clean up (remove all data)
make clean
```

---

## 🔧 Configuration

### LLM Settings
Edit `llm_config.yaml` to customize:
- **Models**: Switch between GPT, Llama, Nemotron, etc.
- **Providers**: NVIDIA, ASTRA, OpenAI, Anthropic
- **Parameters**: Temperature, max_tokens, etc.

```yaml
use_cases:
  chapter_title_generation:
    provider: nvidia
    model: fast              # Change to 'powerful' for better quality
    temperature: 0.7         # Adjust creativity (0.0-1.0)
```

No code changes needed - just edit YAML and restart!

### Add New Provider
```yaml
providers:
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
    models:
      default: gpt-4
```

Then update your use case:
```yaml
use_cases:
  study_material_generation:
    provider: openai         # Switch from nvidia to openai
    model: default
```

---

## 🐛 Troubleshooting

### Can't Connect to Port 7860
```bash
# Check if Gradio is running
make status

# Restart Gradio
make restart-gradio

# Check logs
make logs-gradio
```

### No Space Left on Device
```bash
# Clean up Docker
docker system prune -a

# Check space
df -h
docker system df
```

### Services Won't Start
```bash
# View logs to see what's wrong
make logs-all

# Try full restart
make down
make up
```

### API Key Issues
```bash
# Check environment variables are set
docker exec agenticta env | grep API_KEY

# Re-create .env file with correct key
echo "NVIDIA_API_KEY=nvapi-..." > .env
make restart
```

---

## 📖 Using the LLM Module (Developers)

### Basic Usage
```python
from llm import LLMClient

llm = LLMClient()

# Make a call
response = await llm.call(
    prompt="Explain photosynthesis",
    use_case="study_material_generation"
)

# Stream response
async for chunk in llm.stream(
    prompt="Create study notes...",
    use_case="study_material_generation"
):
    print(chunk, end="", flush=True)
```

### Available Use Cases
See `llm_config.yaml` for all configured use cases:
- `chapter_title_generation` - Generate chapter titles
- `subtopic_title_generation` - Generate subtopic titles
- `study_material_generation` - Create study materials
- `curriculum_modification` - Modify curriculum based on feedback
- `document_search_rerank` - Rerank search results

### Override Parameters
```python
response = await llm.call(
    prompt="...",
    use_case="study_material_generation",
    max_tokens=100000,        # Override default
    temperature=0.9,          # More creative
)
```

---

## 🏗️ Architecture

```
AgenticTA/
├── docker-compose.yml       # Service orchestration
├── Makefile                 # Commands (make help)
├── llm_config.yaml          # LLM configuration
├── gradioUI.py              # Web interface
├── nodes.py                 # Core orchestration
├── llm/                     # LLM module
│   ├── client.py           # Main LLMClient
│   ├── config.py           # Config loader
│   ├── providers/          # Provider implementations
│   │   ├── nvidia.py
│   │   └── astra.py
│   └── handlers.py         # Use case handlers
└── rag/                     # RAG services (submodule)
```

---

## 📚 Learn More

- **Setup Guide**: `SETUP_GUIDE.md` - Detailed setup instructions
- **LLM Module**: `llm/README.md` - Module architecture
- **Config**: `llm_config.yaml` - All LLM settings

---

## 💡 Tips

1. **Start Small**: Test with 1-2 PDFs first
2. **Monitor Logs**: Use `make logs-gradio` to debug issues
3. **GPU Memory**: If running out of memory, reduce `max_tokens` in config
4. **Cache Results**: First curriculum generation is slow, subsequent ones are faster
5. **Clean PDFs**: Remove old PDFs from `pdfs/` folder before uploading new ones

---

## ✅ Quick Test

```bash
# 1. Start everything
make up && sleep 30 && make gradio

# 2. Test LLM module
make test

# 3. Open browser
# Visit http://localhost:7860

# 4. Upload a PDF and test!
```

---

**Need Help?** Check `make help` for all available commands.

