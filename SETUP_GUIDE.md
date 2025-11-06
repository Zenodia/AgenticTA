# AgenticTA Setup Guide

Simple guide to start the AgenticTA application and all its dependencies.

## Prerequisites

- Docker with GPU support
- NVIDIA GPU drivers
- Environment variables set (see `envsetup.sh`)

---

## 🚀 Quick Start (2 Commands!)

```bash
# 1. Start everything
make up

# 2. Start Gradio UI
make gradio

# 3. Open browser
open http://localhost:7860
```

That's it! All services are now running. 🎉

---

## 📋 Available Commands

### Essential Commands

```bash
make up          # Start all services (builds automatically)
make down        # Stop all services
make gradio      # Start Gradio UI
make status      # Show what's running
make logs        # View logs
```

### Development Commands

```bash
make shell       # Enter container shell
make test        # Test LLM module
make restart     # Restart everything
make clean       # Clean up everything
```

### Advanced Commands

```bash
make build           # Build image only
make rebuild         # Full rebuild from scratch
make health          # Check service health
make info            # Show service information
make logs-gradio     # View Gradio logs
make logs-rag        # View RAG server logs
make logs-all        # View all logs
make restart-gradio  # Restart Gradio only
```

---

## 🎯 What `make up` Does

Starts all required services in the correct order:

1. **milvus-etcd** - Milvus metadata store
2. **milvus-minio** - Milvus object storage  
3. **milvus-standalone** - Vector database
4. **redis** - Caching layer
5. **nv-ingest-ms-runtime** - NV Ingest runtime
6. **ingestor-server** - Document ingestion service
7. **rag-server** - RAG backend
8. **rag-frontend** - RAG web interface
9. **agenticta** - Your application

✅ Automatically handles:
- Service dependencies
- Health checks
- Network configuration
- Volume management
- GPU allocation

---

## 🌐 Service URLs

Once running, access services at:

| Service | URL | Purpose |
|---------|-----|---------|
| **Gradio UI** | http://localhost:7860 | Main application interface |
| **RAG Server** | http://localhost:8081 | Document search/retrieval |
| **RAG Frontend** | http://localhost:8090 | RAG UI (optional) |
| **Ingestor** | http://localhost:8082 | Document ingestion |
| **Milvus** | http://localhost:19530 | Vector database |
| **Redis** | http://localhost:6379 | Caching |

---

## 📖 Step-by-Step Guide

### First Time Setup

```bash
# 1. Clone repository (if not already done)
cd /home/ubuntu/AgenticTA

# 2. Set environment variables
source envsetup.sh

# 3. Start all services
make up
# This will:
# - Build the Docker image
# - Start all 9 services
# - Wait for health checks
# - Show you the URLs

# 4. Start Gradio UI
make gradio

# 5. Open browser to http://localhost:7860
```

### Daily Workflow

```bash
# Morning - start services if stopped
make up

# Check what's running
make status

# Start Gradio
make gradio

# During development
make logs        # Watch logs
make shell       # Debug in container
make test        # Test LLM module

# End of day (optional - can leave running)
make down        # Stop all services
```

---

## 🔍 Troubleshooting

### Check Service Status

```bash
# View all services
make status

# Check specific service logs
make logs-gradio
make logs-rag

# Check health
make health
```

### Common Issues

**"Container already exists"**
```bash
make down
make up
```

**"Port already in use"**
```bash
# Find process using port
sudo lsof -i :7860

# Stop all services and restart
make restart
```

**"Service unhealthy"**
```bash
# Check logs
make logs-rag

# Restart specific service
docker compose restart rag-server

# Or restart everything
make restart
```

**"Build failed"**
```bash
# Clean rebuild
make rebuild
```

**"Gradio not responding"**
```bash
# Restart Gradio only
make restart-gradio

# Check logs
make logs-gradio
```

---

## 🧪 Testing

### Test LLM Module

```bash
# Quick test
make test

# Manual test in container
make shell
python3 -c "from llm import LLMClient; print('OK')"
exit

# Run examples
docker compose exec agenticta python3 llm_example_usage.py
```

### Test RAG Services

```bash
# Check RAG server
curl http://localhost:8081/v1/health

# Check Ingestor
curl http://localhost:8082/v1/health

# Full health check
make health
```

---

## 🔄 Updating

### After Code Changes

```bash
# If Python code changed
make restart-gradio

# If Dockerfile changed
make rebuild

# If requirements.txt changed
make rebuild
```

### Updating Dependencies

```bash
# Edit requirements.txt
vim requirements.txt

# Rebuild
make rebuild
```

---

## 📊 Monitoring

### View Logs

```bash
# All logs
make logs-all

# AgenticTA logs
make logs

# Gradio logs
make logs-gradio

# RAG server logs
make logs-rag

# Specific service
docker compose logs -f milvus
```

### Check Resources

```bash
# Container stats
docker stats

# Disk usage
docker system df

# Service status
make status
```

---

## 🧹 Cleanup

### Stop Services

```bash
# Stop all services
make down

# Stop and remove volumes
make clean

# Full cleanup including images
make clean
docker image prune -a
```

### Reset Everything

```bash
# Nuclear option - start fresh
make clean
make rebuild
```

---

## 🎓 Understanding the Stack

### Service Dependencies

```
milvus-etcd + milvus-minio
    ↓
milvus-standalone
    ↓
rag-server + ingestor-server (depends on redis, nv-ingest)
    ↓
rag-frontend
    ↓
agenticta (your app)
```

### Data Flow

```
1. User uploads PDF → Gradio UI (port 7860)
2. PDF sent to → Ingestor (port 8082)
3. Vectors stored in → Milvus (port 19530)
4. User queries → RAG Server (port 8081)
5. Results shown in → Gradio UI
```

---

## 🔧 Configuration

### Environment Variables

Set in `envsetup.sh` or `.env`:

```bash
NVIDIA_API_KEY=nvapi-xxx...      # Required
ASTRA_TOKEN=xxx...               # Optional
HF_TOKEN=xxx...                  # Optional
```

### LLM Configuration

Edit `llm_config.yaml` to:
- Change providers (nvidia, astra)
- Adjust models
- Modify use cases
- Set parameters (temperature, max_tokens)

### Docker Compose

Edit `docker-compose.yml` to:
- Change ports
- Add volumes
- Modify resource limits
- Add new services

---

## 💡 Tips & Best Practices

### Performance

- **Keep services running** between sessions (faster restarts)
- **Use `make logs-gradio`** to monitor UI in real-time
- **GPU allocation** is automatic via Docker Compose

### Development

- **Use `make shell`** to debug inside container
- **Edit files locally**, changes sync to container via volume mount
- **Use `make restart-gradio`** for quick Python code changes

### Production

- Set proper resource limits in `docker-compose.yml`
- Use health checks for monitoring
- Configure log rotation
- Set up alerts for service failures

---

## 📚 Additional Resources

- **LLM Module**: See `llm/README.md`
- **Migration Guide**: See `LLM_MIGRATION_GUIDE.md`
- **Quick Reference**: See `LLM_QUICK_REFERENCE.md`
- **Compose Options**: See `COMPOSE_OPTIONS.md`

---

## ❓ FAQ

**Q: Do I need to rebuild after changing Python code?**  
A: No, just `make restart-gradio`. Files are mounted.

**Q: Can I run without GPU?**  
A: No, GPU is required for the ML models.

**Q: Where are logs stored?**  
A: Gradio logs: `/tmp/gradio.log` in container. Others: `docker compose logs`

**Q: How do I access the container?**  
A: `make shell`

**Q: Can I run multiple instances?**  
A: Not on the same ports. Change ports in `docker-compose.yml`.

**Q: Where is the data stored?**  
A: Volumes in `./rag/deploy/compose/volumes/` directory.

---

## 🎉 Success!

If you can access http://localhost:7860 and see the Gradio UI, you're all set!

Try:
1. Upload a PDF
2. Generate curriculum
3. Chat with study buddy
4. Take a quiz

Enjoy AgenticTA! 🚀
