# AgenticTA

AI-powered teaching assistant for generating personalized study materials from PDFs.

## 🚀 Get Started

```bash
# 1. Set your API key
echo "NVIDIA_API_KEY=nvapi-..." > .env

# 2. Start services
make up && sleep 30 && make gradio

# 3. Open http://localhost:7860
```

**📖 Full Guide**: See [QUICKSTART.md](QUICKSTART.md)

---

## Features

- **Smart Curriculum Generation** - AI analyzes PDFs and creates learning paths
- **Interactive Study Materials** - Generated study guides with examples
- **Study Buddy Chat** - Ask questions about your materials
- **RAG-Powered** - Retrieval-augmented generation for accurate answers
- **Scalable LLM Integration** - Supports multiple AI providers

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get up and running fast (all 4 modes)
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed setup instructions
- **[llm/README.md](llm/README.md)** - LLM module architecture
- **[vault/](vault/)** - Vault integration documentation

---

## Quick Commands

```bash
make help              # View all commands
make up                # Start all services (uses .env)
make up-with-vault     # Start with Vault (dev mode)
make gradio            # Start Gradio UI
make logs              # View logs
make restart           # Restart services
make shell             # Enter container
make down              # Stop everything
make clean             # Clean up all data
```

**💡 Tip**: Use `make up` for fast dev, `make up-with-vault` to test Vault integration

---

## Architecture

```
AgenticTA/
├── gradioUI.py              # Web interface
├── nodes.py                 # Orchestration logic
├── llm/                     # Scalable LLM module
│   ├── providers/          # NVIDIA, ASTRA, etc.
│   └── config.py           # Configuration loader
├── llm_config.yaml          # LLM settings
├── docker-compose.yml       # Service orchestration
└── rag/                     # RAG services
```

---

**Requirements**: Docker with GPU support, NVIDIA API key

**License**: See LICENSE files
