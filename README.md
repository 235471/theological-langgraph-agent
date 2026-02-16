<div align="center">

# 📖 Theological LangGraph Agent

**Production-grade multi-agent system for deep biblical analysis**

[![English](https://img.shields.io/badge/English-🇬🇧-blue?style=for-the-badge)](README.md) [![Português (BR)](https://img.shields.io/badge/Português-🇧🇷-green?style=for-the-badge)](README.pt-BR.md)

[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.7-blue)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.12-yellow)](https://www.python.org/)
[![Render](https://img.shields.io/badge/Deploy-Render-blueviolet)](https://render.com/)

</div>

A multi-agent theological analysis system built with **LangGraph**, **FastAPI**, and **Google Gemini**. It performs parallel biblical exegesis across four specialized agents — panorama, lexical, historical-theological, and intertextual — validated by a theological review layer and governed by caching, auditing, and Human-in-the-Loop (HITL) controls.

> 📄 **[Technical Reference](docs/technical-reference.md)** — Implementation details, code patterns, API reference, and deployment config.

---

## Why This Project?

Biblical exegesis traditionally requires hours of manual research across lexicons, theological commentaries, historical context, and intertextual references. This system compresses that work into a structured, repeatable pipeline.

| Problem | Solution |
|---------|----------|
| Time-consuming manual research | 2-minute multi-dimensional analysis |
| Inconsistent methodology across studies | Structured agent pipeline with validation |
| Limited accessibility for non-scholars | Academic-grade output for anyone |
| No oversight on AI-generated theology | HITL + risk-level gating for doctrinal safety |

**Real-World Impact:** Pastors, seminary students, and Bible study leaders can produce scholarship-level insights without extensive theological training — with built-in safeguards against doctrinal errors.

---

## Architecture

```mermaid
graph TD
    R[Router Function] -->|Send| P[Panorama Agent<br/>FLASH]
    R -->|Send| L[Lexical Agent<br/>FLASH]
    R -->|Send| H[Historical Agent<br/>FLASH]
    R -->|Send| I[Intertextual Agent<br/>LITE]

    P --> J[Join Node]
    L --> J
    H --> J
    I --> J

    J --> V[Theological Validator<br/>TOP]
    V -->|low / medium risk| S[Synthesizer<br/>TOP]
    V -->|high risk| HITL[HITL Pending<br/>Email Alert]

    S --> OUT[Final Analysis]
    HITL --> END[Halted — Awaiting Review]

    style R fill:#ff6b6b,color:#fff
    style J fill:#4ecdc4,color:#fff
    style V fill:#f9a825,color:#fff
    style S fill:#45b7d1,color:#fff
    style HITL fill:#e53935,color:#fff
    style OUT fill:#66bb6a,color:#fff
```

**Key patterns:** Scatter-Gather via LangGraph `Send` API · Conditional HITL edge · DRY governance via `_build_node_result()` helper

---

## AI Engineering Decisions

### 3-Tier Model Strategy

Not every agent needs the same model. We distribute load across three tiers to maximize throughput within free-tier rate limits:

| Tier | Model | RPM | Assigned To | Rationale |
|------|-------|-----|-------------|-----------|
| **LITE** | `gemini-2.5-flash-lite` | 10 | Intertextual | Always runs; needs highest throughput |
| **FLASH** | `gemini-2.5-flash` | 5 | Panorama, Lexical, Historical | Good quality-to-speed ratio |
| **TOP** | `gemini-3-flash-preview` | 5 | Validator, Synthesizer | Critical path; needs best reasoning |

Each tier has a **fallback chain** for deprecation resilience: `TOP → FLASH → LITE → gemini-2.0-flash-lite`.

### Human-in-the-Loop (HITL)

The validator agent assesses **theological risk** of each analysis. If risk is `high`:

1. Execution **halts** (graph reaches `END`)
2. Full state is **persisted** to Supabase (`hitl_reviews` table)
3. **Email notification** sent to the reviewer
4. Reviewer can **approve** or **edit-and-approve** via REST endpoint
5. Only the **synthesizer re-runs** — no redundant agent execution

> **Design choice:** We halt instead of auto-correcting because theological errors require human judgment, not automated fixes.

### Governance at Zero Additional Cost

Every LLM call already returns `usage_metadata`. We extract it and propagate through the graph state:

- **Token tracking** per node (`tokens_consumed`)
- **Model versions** used (`model_versions`)
- **Reasoning trail** with timing (`reasoning_steps`)
- **Structured JSON logs** with `run_id` correlation

This gives full observability without any extra API calls or external services.

### Caching Strategy

Identical requests (same book + chapter + verses + modules) are cached using **SHA-256 hashing**:
- Cache key = deterministic hash of input parameters
- Atomic hit counting (race-condition safe)
- Returns cached result with `from_cache: true` flag

---

## Key Features

- **Parallel Agent Execution** — Scatter-gather via LangGraph `Send` API
- **Hybdrid LLM Output** — Raw Markdown for analysis nodes + Pydantic validation for governance
- **HITL Gating** — Risk-based conditional edge with email alerts
- **Caching** — SHA-256 dedup with atomic hit counting
- **Audit Trail** — Every run persisted (success + failure) to PostgreSQL
- **JSON/YAML Structured Logging** — Machine-parseable logs with `run_id` correlation (see [`samples/`](samples/))
    > **Engineering Insight:** The architecture is **Observable-by-Design**. Through structured logs (JSON/YAML), we capture atomic token consumption and latency for every agent. This enables not just security auditing (risk_level), but precise financial analysis (ROI) and continuous UX optimization.
- **Fallback Chain** — Automatic model fallback on 429/deprecation
- **Docker + Render** — Production deployment with keep-alive cron
- **LangSmith Integration** — Full observability and tracing

---

## Quick Start

### Prerequisites
- Python 3.12+
- [Google Gemini API Key](https://ai.google.dev/) (free tier supported)
- [Supabase](https://supabase.com/) project (free tier — PostgreSQL)
- Optional: [LangSmith API Key](https://smith.langchain.com/) for tracing

### Installation

```bash
git clone https://github.com/235471/theological-langgraph-agent.git
cd theological-langgraph-agent

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your keys
```

### Environment Variables

```env
# Required
GOOGLE_API_KEY=your_gemini_api_key
DB_URL=postgresql://postgres:password@db.project.supabase.co:5432/postgres

# HITL Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
HITL_REVIEWER_EMAIL=reviewer@example.com

# Optional — Observability
LANGSMITH_API_KEY=lsv2_pt_xxxxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=TheologicalAgent
```

### Run

```bash
python start_dev.py
```

This starts:
- **FastAPI** at `http://localhost:8000` (API docs at `/docs`)
- **Streamlit** at `http://localhost:8501` (frontend)

---

## Deployment

### API — Render (Docker)

The project includes a `Dockerfile` and `render.yaml` for one-click deploy:

1. Import repo on [Render](https://render.com/)
2. It detects `render.yaml` and creates the service
3. Set secrets in the Render dashboard (`GOOGLE_API_KEY`, `DB_URL`, etc.)
4. GitHub Actions keep-alive pings `/health` every 14 minutes

### Frontend — Streamlit Cloud

1. Connect repo on [Streamlit Cloud](https://streamlit.io/cloud)
2. Set `API_BASE_URL` secret pointing to your Render URL
3. Deploy

> See [DEPLOYMENT.md](./documents/DEPLOYMENT.md) for detailed instructions.

---

## Output Example

**Input:** João 8:31-34 (Full mode: panorama + exegese + teologia)

**Output Preview:**

> ### A Verdadeira Liberdade: Discipulado, Verdade e a Quebra das Correntes do Pecado
>
> **Contextualização** — Situada no "Livro dos Sinais" (João 1-12), esta perícope ocorre após o sinal da cura do cego de nascença...
>
> **Exegese Lexical** — *Permanência (μένω - menō):* Subjuntivo aoristo indicando estado contínuo de habitação...
>
> **Intertextualidade** — Jesus atua como o Novo Libertador, ecoando Êxodo 20:2...

Full output (3,500 words): [`examples/joao-8v31-34.md`](examples/joao-8v31-34.md)

---

## Project Structure

```
theological-langgraph-agent/
├── src/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── agentState.py          # LangGraph state (TypedDict + governance fields)
│   │   │   ├── build.py               # Graph construction, nodes, _build_node_result()
│   │   │   └── model.py               # Pydantic schemas (AnalysisOutput, ValidatorOutput)
│   │   ├── client/
│   │   │   └── client.py              # 3-tier model strategy + fallback chain
│   │   ├── controller/
│   │   │   ├── analyze_controller.py   # POST /analyze
│   │   │   ├── bible_controller.py     # GET /bible/{abbrev}/{chapter}/verses
│   │   │   ├── hitl_controller.py      # HITL endpoints (pending, approve, edit)
│   │   │   └── debug_controller.py     # Health & debug endpoints
│   │   ├── service/
│   │   │   ├── analysis_service.py     # Orchestrates cache → agent → audit
│   │   │   ├── bible_service.py        # Bible data access
│   │   │   ├── cache_service.py        # SHA-256 cache with atomic hits
│   │   │   ├── audit_service.py        # Run persistence (success + failure)
│   │   │   ├── hitl_service.py         # HITL CRUD operations
│   │   │   └── email_service.py        # SMTP email notifications
│   │   ├── database/
│   │   │   ├── connection.py           # PostgreSQL pool (Supabase)
│   │   │   └── init_db.py             # Idempotent table bootstrap
│   │   ├── utils/
│   │   │   ├── prompts.py             # System prompts (all agents)
│   │   │   └── logger.py             # JSON structured logging
│   │   └── schemas.py                 # Pydantic request/response + HITL schemas
│   └── main.py                        # FastAPI app with lifespan events
├── streamlit/
│   ├── streamlit_app.py               # Frontend with governance badges
│   ├── api_client.py                  # HTTP client with local fallback
│   ├── bible_books.py                 # Book metadata
│   └── style.css                      # Custom styling
├── Dockerfile                          # API-only Docker image
├── render.yaml                         # Render IaC blueprint
├── requirements.txt                    # Full dependencies
├── requirements-api.txt                # API-only dependencies (Docker)
└── .github/workflows/keep-alive.yml   # Keep-alive cron (14min)
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Run theological analysis |
| `GET` | `/bible/{abbrev}/{chapter}/verses` | Get chapter verses |
| `GET` | `/hitl/pending` | List pending HITL reviews |
| `GET` | `/hitl/{run_id}` | Get review details |
| `POST` | `/hitl/{run_id}/approve` | Approve or edit-and-approve |
| `GET` | `/health` | Health check (DB, uptime, version) |
| `GET` | `/debug/test-llm` | Test LLM connectivity |

Full API docs: `http://localhost:8000/docs`

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE).

## Acknowledgments

- **LangGraph** — Multi-agent orchestration framework
- **Google Gemini** — LLM API (free tier)
- **Supabase** — PostgreSQL hosting (free tier)
- **FastAPI** & **Streamlit** communities
- Bible translation: Nova Almeida Atualizada (NAA)

---

<div align="center">

**Built with LangGraph · FastAPI · Streamlit · Google Gemini**

</div>
