# 🚀 Deployment Guide

This guide covers deploying the Theological LangGraph Agent to **Render** (Backend/API) and **Streamlit Cloud** (Frontend).

## 🏗️ Architecture

- **Backend (API):** FastAPI with LangGraph connected to Google Gemini and Supabase PostgreSQL. Hosted on Render.
- **Frontend (UI):** Streamlit application. Hosted on Streamlit Cloud.
- **Database:** Supabase PostgreSQL (Transaction Pooler - port 6543).

---

## ☁️ 1. Backend Deployment (Render)

Render is used to host the FastAPI application.

### Prerequisites
- [Render Account](https://render.com/)
- [Supabase Project](https://supabase.com/) (PostgreSQL Database)
- Google Gemini API Key
- GitHub Repository

### Step 1: Database Setup (Supabase)
1. Determine your **Transaction Pooler URL**:
   - Go to Supabase Dashboard → Settings → Database → Connection Pooling.
   - Mode: `Transaction`.
   - Port: `6543`.
   - Copy the connection string. It looks like:
     `postgres://postgres.xxxx:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require`

### Step 2: Render Configuration
1. **New Web Service**: Connect your GitHub repository.
2. **Runtime**: `Docker` (We use a custom Dockerfile).
3. **Region**: Choose one close to your database (e.g., Oregon/US-West).
4. **Branch**: `main`.
5. **Environment Variables**:
   Add the following secrets in the Render dashboard:
   
   | Key | Value | Description |
   |-----|-------|-------------|
   | `GOOGLE_API_KEY` | `AIzaSy...` | Gemini API Key |
   | `DB_URL` | `postgresql://...` | Supabase Transaction Pooler URL (Port 6543). **Do NOT add params**. |
   | `LANGCHAIN_TRACING_V2` | `true` | Enable LangSmith tracing |
   | `LANGCHAIN_PROJECT` | `TheologicalAgent-Prod` | LangSmith Project Name |
   | `LANGSMITH_API_KEY` | `lsv2_...` | LangSmith API Key |
   | `PORT` | `10000` | Render expects the app to bind to this port |

### Step 3: Deploy
- Click **Create Web Service**.
- The build process will:
  1. Install Python dependencies from `requirements-api.txt`.
  2. Copy source code (`src/`) and resources (`resources/NAA.json`).
  3. Start the application with `uvicorn`.

**Verification:**
- Visit `https://your-service-name.onrender.com/health`.
- Expect: `{"status": "healthy", "database": "connected"}`.

---

## 🎨 2. Frontend Deployment (Streamlit Cloud)

Streamlit Cloud hosts the user interface.

### Step 1: Create App
1. Go to [share.streamlit.io](https://share.streamlit.io).
2. Click **New app**.
3. Select your repository and branch (`main`).
4. **Main file path**: `streamlit/streamlit_app.py`.

### Step 2: Configure Secrets
Go to **Advanced Settings** -> **Secrets** and add:

```toml
# URL of your Render backend (NO trailing slash)
API_BASE_URL = "https://your-service-name.onrender.com"

# Optional: Tracing for the frontend process locally (if running locally)
# Not strictly needed for Cloud if API handles the logic
LANGCHAIN_TRACING_V2 = "true"
LANGCHAIN_PROJECT = "TheologicalAgent-Frontend"
LANGSMITH_API_KEY = "lsv2_..."
```

### Step 3: Deploy
- Click **Deploy**.
- The app will install dependencies from `requirements.txt` (root) which includes `streamlit`.

---

## 🛠️ Troubleshooting & Key Configurations

### Database Connection (Crucial!)
- **Issue:** `prepared statement ... already exists` or `cannot insert multiple commands`.
- **Cause:** Incompatibility between `psycopg` default prepared statements and Supabase Transaction Pooler (PgBouncer).
- **Solution:** The codebase is already patched.
  - `connection.py`: Sets `prepare_threshold=None` to disable prepared statements.
  - `init_db.py`: Uses `prepare=False` for DDL statements.
  - **Do NEVER change** `prepare_threshold` back to `0` or default.

### Docker Build
- **Issue:** `NAA.json` not found or Bible verses missing.
- **Solution:** The `Dockerfile` must strictly include:
  ```dockerfile
  COPY resources /app/resources
  ```
  And `.dockerignore` **must not** ignore the `resources/` folder.

### Cold Start
- Render Free Tier spins down after inactivity.
- On first request, the Streamlit app might timeout (5s default).
- **Fix:** Access the API `/health` endpoint manually to wake it up before presenting the demo. Future updates will increase frontend timeout.

---

## 🔄 CI/CD Pipeline

- **Backend:** Pushing to `main` triggers automatic redeploy on Render.
- **Frontend:** Pushing to `main` triggers automatic redeploy on Streamlit Cloud.
