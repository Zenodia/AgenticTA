# AgenticTA Quickstart

Get running in 3 minutes.

---

## ⚡ Fast Start

```bash
# 1. Set your API key
echo "NVIDIA_API_KEY=nvapi-..." > .env

# 2. Start everything (wait ~30 seconds)
make up

# 3. Start Gradio UI
make gradio

# 4. Open http://localhost:7860
```

That's it! 🎉

---

## 📖 Upload & Study

1. **Upload PDFs** → Click "Upload PDF files" button
2. **Generate** → Click "Generate Curriculum" (takes 2-3 min)
3. **Study** → Browse chapters, ask Study Buddy questions

---

## 🛠️ Essential Commands

```bash
make help       # Show all commands
make status     # Check what's running
make logs       # View logs
make restart    # Restart everything
make down       # Stop everything
```

---

## 🔧 Quick Config Changes

Want different AI models? Edit `llm_config.yaml`:

```yaml
use_cases:
  study_material_generation:
    provider: nvidia
    model: powerful      # Change to 'fast' for speed
    temperature: 0.7     # Adjust 0.0-1.0
```

Then `make restart`

---

## ⚠️ Common Issues

**Can't connect to port 7860?**
```bash
make restart-gradio && make logs-gradio
```

**No space left?**
```bash
docker system prune -a
```

**Services won't start?**
```bash
make down && make up
```

---

## 📚 Need More Help?

- **Detailed Setup**: See [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **LLM Module**: See [llm/README.md](llm/README.md)
- **All Commands**: Run `make help`
