# 🚀 Deployment Guide

This guide covers deploying the Theological LangGraph Agent to various platforms.

## Streamlit Cloud Deployment

Streamlit Cloud provides free hosting for Streamlit apps with the following limitations:
- 1GB RAM
- Shared CPU
- 1GB storage

### Prerequisites

1. GitHub account
2. Streamlit Cloud account (free at [share.streamlit.io](https://share.streamlit.io))
3. Google Gemini API key ([Get one free](https://ai.google.dev/))

### Step 1: Prepare Repository

Ensure your repository has:
- ✅ `requirements.txt` (generated below)
- ✅ `.streamlit/config.toml` (generated below)
- ✅ `streamlit/app.py` as main entry point
- ✅ `.gitignore` excluding `.env` and `venv/`

### Step 2: Push to GitHub

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Theological LangGraph Agent"

# Create repository on GitHub and push
git remote add origin https://github.com/yourusername/theological-langgraph-agent.git
git branch -M main
git push -u origin main
```

### Step 3: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"

2. **Connect Repository**
   - Repository: `yourusername/theological-langgraph-agent`
   - Branch: `main`
   - Main file path: `streamlit/app.py`

3. **Configure Secrets**
   Click "Advanced settings" → "Secrets" and add:
   
   ```toml
   GOOGLE_API_KEY = "your_gemini_api_key_here"
   LANGSMITH_API_KEY = "your_langsmith_key_here"  # Optional
   LANGCHAIN_TRACING_V2 = "true"                  # Optional
   LANGCHAIN_PROJECT = "TheologicalAgent"         # Optional
   ```

4. **Deploy**
   - Click "Deploy!"
   - Wait 2-3 minutes for initial build
   - Your app will be live at `https://yourusername-theological-agent.streamlit.app`

### Step 4: Update Backend URL

The Streamlit Cloud deployment needs to point to a hosted backend. You have two options:

#### Option A: Deploy Backend Separately

Deploy the FastAPI backend to:
- **Railway.app** (recommended for free tier)
- **Render.com**
- **Google Cloud Run**
- **AWS Lambda** (with Mangum adapter)

Then update `streamlit/api_client.py`:

```python
# For production
API_BASE_URL = "https://your-backend.railway.app"

# For development
# API_BASE_URL = "http://localhost:8000"
```

#### Option B: Monolith Mode (All-in-One)

Run both Streamlit and FastAPI in a single process:

1. Create `streamlit_with_backend.py`:

```python
import subprocess
import os
import time
import threading

def start_backend():
    """Start FastAPI in background thread."""
    os.chdir("src")
    os.environ["PYTHONPATH"] = "."
    subprocess.run([
        "uvicorn", "main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000"
    ])

if __name__ == "__main__":
    # Start backend in background
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    
    # Give backend time to start
    time.sleep(5)
    
    # Start Streamlit (this blocks)
    subprocess.run(["streamlit", "run", "streamlit/app.py"])
```

2. Update Streamlit Cloud settings:
   - Main file path: `streamlit_with_backend.py`

⚠️ **Note**: Monolith mode may exceed Streamlit Cloud's 1GB RAM limit for heavy workloads.

### Troubleshooting

#### "Module not found" errors

Ensure `requirements.txt` includes all dependencies:
```bash
pip freeze > requirements.txt
```

#### API timeout errors

Increase timeout in `streamlit/api_client.py`:
```python
timeout = 120  # 2 minutes for long analyses
```

#### Memory errors

Reduce concurrent agent execution or use smaller models.

---

## Railway.app Deployment (Backend)

Railway offers 500 hours/month free tier.

### Step 1: Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### Step 2: Initialize Project

```bash
# In your project directory
railway init
```

### Step 3: Configure

Create `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd src && uvicorn main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

Create `Procfile`:

```
web: cd src && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Step 4: Set Environment Variables

```bash
railway variables set GOOGLE_API_KEY=your_key_here
railway variables set LANGSMITH_API_KEY=your_langsmith_key
```

### Step 5: Deploy

```bash
railway up
```

Your API will be live at `https://your-project.railway.app`

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY resources/ ./resources/
COPY .env.example .env

# Expose ports
EXPOSE 8000 8501

# Start both services
CMD ["python", "start_dev.py"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  theological-agent:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    volumes:
      - ./resources:/app/resources:ro
    restart: unless-stopped
```

### Build and Run

```bash
docker-compose up --build
```

---

## Performance Optimization

### 1. Caching

Enable caching in `streamlit/app.py`:

```python
@st.cache_data(ttl=3600)
def get_cached_verses(book, chapter):
    return api_client.get_verses(book, chapter)
```

### 2. Connection Pooling

Use `httpx.AsyncClient` with connection pooling in `api_client.py`.

### 3. Database Migration

For production, migrate from JSON to PostgreSQL:

```bash
pip install sqlalchemy asyncpg
```

---

## Monitoring

### LangSmith Tracing

Enable in production for debugging:

```env
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=lsv2_pt_xxxxx
LANGCHAIN_PROJECT=TheologicalAgent-Prod
```

### Application Logs

View logs in Streamlit Cloud:
- Dashboard → App → Logs

View logs in Railway:
```bash
railway logs
```

---

## Cost Estimation

### Free Tier Usage

| Service | Limit | Usage |
|---------|-------|-------|
| Streamlit Cloud | 1 app | 1 app |
| Railway.app | 500h/month | ~720h needed |
| Google Gemini | 1500 requests/day | Varies |

**Recommended**: 
- Streamlit Cloud (free) for frontend
- Railway.app (free 500h + $5/month after) for backend
- Google Gemini free tier

**Total monthly cost**: ~$5/month

---

## Security Best Practices

1. **Never commit `.env`**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use secrets management**
   - Streamlit Cloud: Dashboard secrets
   - Railway: Environment variables
   - Docker: `.env` file mounted as volume

3. **Rotate API keys regularly**

4. **Set CORS origins explicitly**
   ```python
   allow_origins=["https://yourusername-theological-agent.streamlit.app"]
   ```

5. **Add rate limiting**
   ```bash
   pip install slowapi
   ```

---

## Backup & Recovery

### Database Backup

```bash
# Backup NAA.json
aws s3 cp resources/NAA.json s3://your-bucket/backups/
```

### Environment Backup

Store `.env.example` with documentation, never the actual `.env`.

---

## Rollback Strategy

### Streamlit Cloud

Revert to previous commit:
```bash
git revert HEAD
git push
```
Streamlit auto-redeploys.

### Railway

```bash
railway rollback
```

---

## Support

For deployment issues:
- Streamlit: [docs.streamlit.io](https://docs.streamlit.io)
- Railway: [docs.railway.app](https://docs.railway.app)
- LangGraph: [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph)

---

**Happy Deploying! 🚀**
