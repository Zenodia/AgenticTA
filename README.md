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
- **quiz generation per sub topic** - generating multi-choice quizes to test your knowledge
- **self-improve** - minimal imlplementation self-refinement via natural langauge feedback improved via prompt mutation.
- **Study Buddy Chat** - Ask questions about your materials
- **RAG-Powered** - leveraging NVIDIA's NeMo Retriever NIM as RAG (Retrieval-Augmented Generation) enhancing study-buddy conversations.
- **Scalable LLM Integration** - Supports multiple AI providers bute tested on NVIDIA's NIM LLMs

---

## Documentation

### Development
- **[QUICKSTART.md](QUICKSTART.md)** - Get up and running fast (all 4 modes)
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed setup instructions
- **[llm/README.md](llm/README.md)** - LLM module architecture

### Production Deployment 🚀
- **[PRODUCTION_QUICKSTART.md](docs/PRODUCTION_QUICKSTART.md)** - Deploy to Artifactory in 5 minutes ⭐
- **[docs/ARTIFACTORY_DEPLOYMENT.md](docs/ARTIFACTORY_DEPLOYMENT.md)** - Complete deployment guide
- **[docs/VAULT_DEPLOYMENT_GUIDE.md](docs/VAULT_DEPLOYMENT_GUIDE.md)** - Vault setup & token management
- **[docs/vault-workflow-diagram.md](docs/vault-workflow-diagram.md)** - Visual workflows

### Code & Utilities
- **[vault/](vault/)** - Vault integration code
- **[docs/](docs/)** - All documentation

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
