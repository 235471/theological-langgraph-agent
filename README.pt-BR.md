<div align="center">

# 📖 Theological LangGraph Agent

**Sistema multi-agente de nível produção para análise bíblica profunda**

[![English](https://img.shields.io/badge/English-🇬🇧-blue?style=for-the-badge)](README.md) [![Português (BR)](https://img.shields.io/badge/Português-🇧🇷-green?style=for-the-badge)](README.pt-BR.md)

[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.7-blue)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Latest-red)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.12-yellow)](https://www.python.org/)
[![Render](https://img.shields.io/badge/Deploy-Render-blueviolet)](https://render.com/)

</div>

Sistema de análise teológica multi-agente construído com **LangGraph**, **FastAPI** e **Google Gemini**. Executa exegese bíblica em paralelo através de quatro agentes especializados — panorama, léxico, histórico-teológico e intertextual — validados por uma camada de revisão teológica e governados por cache, auditoria e controles Human-in-the-Loop (HITL).

> 📄 **[Referência Técnica](docs/technical-reference.pt-BR.md)** — Detalhes de implementação, padrões de código, referência de API e configuração de deploy.

---

## Por Que Este Projeto?

A exegese bíblica tradicionalmente requer horas de pesquisa manual em léxicos, comentários teológicos, contexto histórico e referências intertextuais. Este sistema comprime esse trabalho em um pipeline estruturado e reprodutível.

| Problema | Solução |
|----------|---------|
| Pesquisa manual demorada | Análise multidimensional em 2 minutos |
| Metodologia inconsistente entre estudos | Pipeline estruturado com validação |
| Acessibilidade limitada para não-acadêmicos | Resultado de nível acadêmico para qualquer pessoa |
| Sem supervisão sobre teologia gerada por IA | HITL + classificação de risco para segurança doutrinária |

**Impacto Real:** Pastores, seminaristas e líderes de estudo bíblico podem produzir insights de nível acadêmico sem treinamento teológico extensivo — com salvaguardas contra erros doutrinários.

---

## Arquitetura

```mermaid
graph TD
    R[Função Router] -->|Send| P[Agente Panorama<br/>FLASH]
    R -->|Send| L[Agente Léxico<br/>ADK + FLASH]
    R -->|Send| H[Agente Histórico<br/>FLASH]
    R -->|Send| I[Agente Intertextual<br/>LITE]

    P --> J[Nó de Junção]
    L --> J
    H --> J
    I --> J

    J --> V[Validador Teológico<br/>TOP]
    V -->|risco baixo / médio| S[Sintetizador<br/>TOP]
    V -->|risco alto| HITL[HITL Pendente<br/>Alerta por Email]

    S --> OUT[Análise Final]
    HITL --> END[Pausado — Aguardando Revisão]

    style R fill:#ff6b6b,color:#fff
    style J fill:#4ecdc4,color:#fff
    style V fill:#f9a825,color:#fff
    style S fill:#45b7d1,color:#fff
    style HITL fill:#e53935,color:#fff
    style OUT fill:#66bb6a,color:#fff
```

**Padrões-chave:** Scatter-Gather via LangGraph `Send` API · Edge condicional HITL · Governança DRY via helper `_build_node_result()`

---

## Decisões de Engenharia de IA

### Estratégia de Modelos em 3 Camadas

Nem todo agente precisa do mesmo modelo. Distribuímos a carga entre três camadas para maximizar o throughput dentro dos limites do free tier:

| Camada | Modelo | RPM | Atribuído A | Justificativa |
|--------|--------|-----|-------------|---------------|
| **LITE** | `gemini-2.5-flash-lite` | 10 | Intertextual | Sempre executa; precisa de maior throughput |
| **FLASH** | `gemini-2.5-flash` | 5 | Panorama, Léxico, Histórico | Boa relação qualidade-velocidade |
| **TOP** | `gemini-3-flash-preview` | 5 | Validador, Sintetizador | Caminho crítico; precisa do melhor raciocínio |

Cada camada tem uma **cadeia de fallback** para resiliência contra depreciação: `TOP → FLASH → LITE → gemini-2.0-flash-lite`.

### Human-in-the-Loop (HITL)

O agente validador avalia o **risco teológico** de cada análise. Se o risco for `high`:

1. A execução **para** (o grafo atinge `END`)
2. O estado completo é **persistido** no Supabase (tabela `hitl_reviews`)
3. **Notificação por email** enviada ao revisor
4. O revisor pode **aprovar** ou **editar e aprovar** via endpoint REST
5. Apenas o **sintetizador re-executa** — sem execução redundante dos agentes

> **Decisão de design:** Paramos em vez de auto-corrigir porque erros teológicos exigem julgamento humano, não correções automatizadas.

### Governança a Custo Zero Adicional

Cada chamada ao LLM já retorna `usage_metadata`. Extraímos e propagamos pelo estado do grafo:

- **Rastreamento de tokens** por nó (`tokens_consumed`)
- **Versões de modelo** utilizadas (`model_versions`)
- **Trilha de raciocínio** com temporização (`reasoning_steps`)
- **Logs JSON estruturados** com correlação `run_id`

Isso proporciona observabilidade completa sem chamadas de API adicionais ou serviços externos.

### Exportação Completa de Trace (LangSmith → Supabase)

Para completa governança, auditabilidade, debugging e reprodutibilidade, o sistema captura o trace inteiro de execução (inputs, outputs, pensamentos intermediários e latências) via LangSmith. Após a conclusão, este trace é exportado de forma assíncrona como um arquivo JSON para um **Supabase Storage Bucket** e referenciado com segurança na tabela `graph_run_traces`.

**Exemplo de Registro de Trace:**
```json
[
  {
    "id": 1,
    "run_id": "ab1033f2-710b-49ca-b633-a73e67e6b786",
    "langsmith_run_id": "84dca63c-daca-47ca-a926-50865d4639b2",
    "storage_path": "traces/ab1033f2-710b-49ca-b633-a73e67e6b786.json",
    "size_bytes": 604007,
    "status": "uploaded",
    "error_message": null,
    "created_at": "2026-02-27 18:33:38.838614+00"
  }
]
```

### Agent-in-an-Agent (Grounding com ADK)

O Agente Léxico utiliza o **Agent Development Kit (ADK)** do Google para realizar uma exegese fundamentada em buscas na web. Ao invés de dividir a busca e a geração em múltiplas chamadas ao LLM, implementamos uma **arquitetura ADK de passagem única (single-pass)**:
- O ADK busca autonomamente fontes acadêmicas/lexicográficas e sintetiza o relatório markdown final.
- Mantemos observabilidade completa extraindo profundamente o `usage_metadata` do stream de eventos binários do ADK e canalizando-o para a telemetria central do nosso LangGraph.
- Se o ADK exceder o timeout de `15s` ou não retornar conteúdo de alta qualidade, o nó faz um fallback perfeito para um prompt LangChain legado, rápido e sem grounding.

> 📄 **Aprofundamento:** Consulte a [Referência de Integração ADK](docs/adk-integration.md) (em inglês) para detalhes específicos sobre sincronização de threads, extração de telemetria e o padrão de fallback.

### Gerenciamento de Prompts e Resiliência

A engenharia de prompts é abstraída da base de código principal usando o **LangSmith Prompt Hub**:
- **Hot-swapping:** Os prompts podem ser refinados, testados e publicados na interface do LangSmith sem alterar o código ou exigir redeploy.
- **Fallback Sem Indisponibilidade (Zero-Downtime):** Um script de sincronização (`sync_prompts.py`) faz o download dos prompts publicados para um arquivo local `prompts_fallback.json`. Se o LangSmith ficar offline ou houver rate-limit, o wrapper `hub_fallback.py` captura a exceção de forma transparente, injeta a `GOOGLE_API_KEY` original do ambiente e executa a chamada ao LLM usando a réplica JSON offline.

### Estratégia de Cache

Requisições idênticas (mesmo livro + capítulo + versículos + módulos) são cacheadas usando **hash SHA-256**:
- Chave de cache = hash determinístico dos parâmetros de entrada
- Contagem de hits atômica (segura contra race conditions)
- Retorna resultado cacheado com flag `from_cache: true`

---

## Principais Funcionalidades

- **Execução Paralela de Agentes** — Scatter-gather via LangGraph `Send` API
- **Output Híbrido** — Markdown puro para nós de análise + validação Pydantic para governança
- **Controle HITL** — Edge condicional baseado em risco com alertas por email
- **Cache** — Dedup SHA-256 com contagem atômica de hits
- **Trilha de Auditoria** — Todo run persistido (sucesso + falha) no PostgreSQL
- **Logging JSON/YAML Estruturado** — Logs machine-parseable com correlação `run_id` (ver [`samples/`](samples/))
    > **Insight de Engenharia:** A arquitetura foi desenhada para ser **'Observable-by-Design'**. Através de logs estruturados (JSON/YAML), capturamos o consumo de tokens e a latência de cada agente de forma atômica. Isso permite não apenas a auditoria de segurança (*risk_level*), mas também uma análise financeira precisa (ROI) e a otimização contínua da experiência do usuário (UX).    
- **Prompt Hub + Fallback** — Prompts gerenciados via LangSmith com réplica JSON local para fallback offline
- **Cadeia de Fallback** — Fallback automático de modelo em 429/depreciação
- **Docker + Render** — Deploy em produção com keep-alive cron
- **Integração LangSmith** — Observabilidade e tracing completos

---

## Início Rápido

### Pré-requisitos
- Python 3.12+
- [Google Gemini API Key](https://ai.google.dev/) (free tier suportado)
- Projeto [Supabase](https://supabase.com/) (free tier — PostgreSQL)
- Opcional: [LangSmith API Key](https://smith.langchain.com/) para tracing

### Instalação

```bash
git clone https://github.com/235471/theological-langgraph-agent.git
cd theological-langgraph-agent

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edite .env com suas chaves
```

### Variáveis de Ambiente

```env
# Obrigatórias
GOOGLE_API_KEY=sua_chave_gemini
DB_URL=postgresql://postgres:senha@db.projeto.supabase.co:5432/postgres

# Notificações HITL por Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_app_password
HITL_REVIEWER_EMAIL=revisor@exemplo.com

# Opcional — Observabilidade
LANGSMITH_API_KEY=lsv2_pt_xxxxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=TheologicalAgent

# Opcional — Armazenamento de traces
SUPABASE_PROJECT=https://seu-projeto.supabase.co
SUPABASE_SECRET_KEY=sua_service_role_key_supabase
SUPABASE_TRACES_BUCKET=traces
```

### Executar

```bash
alembic upgrade head
python start_dev.py
```

Isso inicia:
- **FastAPI** em `http://localhost:8000` (docs da API em `/docs`)
- **Streamlit** em `http://localhost:8501` (frontend)

---

## Deploy

### API — Render (Docker)

O projeto inclui `Dockerfile` e `render.yaml` para deploy direto:

1. Importe o repositório no [Render](https://render.com/)
2. Ele detecta o `render.yaml` e cria o serviço
3. Configure os secrets no dashboard do Render (`GOOGLE_API_KEY`, `DB_URL`, `SUPABASE_PROJECT`, `SUPABASE_SECRET_KEY`, etc.)
4. GitHub Actions keep-alive pinga `/health` a cada 14 minutos

### Frontend — Streamlit Cloud

1. Conecte o repositório no [Streamlit Cloud](https://streamlit.io/cloud)
2. Configure o secret `API_BASE_URL` apontando para sua URL do Render
3. Deploy

> Veja [DEPLOYMENT.md](./documents/DEPLOYMENT.md) para instruções detalhadas.

---

## Exemplo de Output

**Input:** João 8:31-34 (Modo Full: panorama + exegese + teologia)

**Preview do Output:**

> ### A Verdadeira Liberdade: Discipulado, Verdade e a Quebra das Correntes do Pecado
>
> **Contextualização** — Situada no "Livro dos Sinais" (João 1-12), esta perícope ocorre após o sinal da cura do cego de nascença...
>
> **Exegese Lexical** — *Permanência (μένω - menō):* Subjuntivo aoristo indicando estado contínuo de habitação...
>
> **Intertextualidade** — Jesus atua como o Novo Libertador, ecoando Êxodo 20:2...

Output completo (3.500 palavras): [`examples/joao-8v31-34.md`](examples/joao-8v31-34.md)

---

## Estrutura do Projeto

```
theological-langgraph-agent/
├── alembic/                    # Migrações baseline do banco de dados
├── docs/                       # Documentação técnica
│   ├── adk-integration.md      # Detalhes do Grounding Léxico ADK
│   ├── db-migrations.md        # Guia de evolução do banco
│   ├── technical-reference.pt-BR.md # Arquitetura completa do sistema
│   └── ...                     # Deep-dives de Hub/Fallback
├── src/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── agentState.py          # Estado LangGraph (TypedDict + campos de governança)
│   │   │   ├── build.py               # Construção do grafo, nós, _build_node_result()
│   │   │   └── model.py               # Schemas Pydantic (AnalysisOutput, ValidatorOutput)
│   │   ├── client/
│   │   │   └── client.py              # Estratégia de 3 camadas + cadeia de fallback
│   │   ├── controller/
│   │   │   ├── analyze_controller.py   # POST /analyze
│   │   │   ├── bible_controller.py     # GET /bible/{abbrev}/{chapter}/verses
│   │   │   ├── hitl_controller.py      # Endpoints HITL (pendente, aprovar, editar)
│   │   │   └── debug_controller.py     # Endpoints de saúde e debug
│   │   ├── service/
│   │   │   ├── analysis_service.py     # Orquestra cache → agente → auditoria
│   │   │   ├── bible_service.py        # Acesso a dados bíblicos
│   │   │   ├── cache_service.py        # Cache SHA-256 com hits atômicos
│   │   │   ├── audit_service.py        # Persistência de runs (sucesso + falha)
│   │   │   ├── hitl_service.py         # Operações CRUD HITL
│   │   │   ├── trace_service.py        # Exportação de traces do LangSmith p/ Supabase
│   │   │   ├── lexical_grounding_service.py # Exegese com grounding web ADK
│   │   │   └── email_service.py        # Notificações email via SMTP
│   │   ├── database/
│   │   │   ├── connection.py           # Pool PostgreSQL (Supabase)
│   │   │   ├── init_db.py             # Bootstrap idempotente de tabelas
│   │   │   └── migrations.py          # Lógica de migrações gerenciadas Alembic
│   │   ├── utils/
│   │   │   ├── hub_fallback.py        # Execução via LangSmith Hub c/ mecanismo de fallback offline
│   │   │   ├── fallbacks/
│   │   │   │   └── prompts_fallback.json # Réplica offline dos prompts do LangSmith
│   │   │   └── logger.py              # Logging JSON estruturado
│   │   └── schemas.py                 # Pydantic request/response + schemas HITL
│   └── main.py                        # App FastAPI com eventos de lifecycle
├── resources/                          # Recursos estáticos
│   └── NAA.json                        # Tradução bíblica local (NAA)
├── samples/                          # Exemplos de logs de auditoria e trace (JSON/YAML)
├── streamlit/
│   ├── streamlit_app.py               # Frontend com badges de governança
│   ├── api_client.py                  # Cliente HTTP com fallback local
│   └── ...
├── alembic.ini                         # Configuração do Alembic
├── start_dev.py                        # Launcher unificado do dev server (API + UI)
├── sync_prompts.py                    # Script para baixar prompts do LangSmith p/ JSON local
├── Dockerfile                          # Imagem Docker só da API
├── render.yaml                         # Blueprint IaC do Render
├── requirements.txt                    # Dependências completas
└── requirements-api.txt                # Dependências só da API (Docker)
```

---

## Endpoints da API

| Método | Caminho | Descrição |
|--------|---------|-----------|
| `POST` | `/analyze` | Executar análise teológica |
| `GET` | `/bible/{abbrev}/{chapter}/verses` | Obter versículos do capítulo |
| `GET` | `/hitl/pending` | Listar revisões HITL pendentes |
| `GET` | `/hitl/{run_id}` | Detalhes da revisão |
| `POST` | `/hitl/{run_id}/approve` | Aprovar ou editar-e-aprovar |
| `GET` | `/health` | Health check (DB, uptime, versão) |
| `GET` | `/debug/test-llm` | Testar conectividade LLM |

Docs completa da API: `http://localhost:8000/docs`

---

## Contribuindo

1. Fork do repositório
2. Crie uma branch (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit das mudanças (`git commit -m 'Add funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

## Licença

MIT License — veja [LICENSE](LICENSE).

## Agradecimentos

- **LangGraph** — Framework de orquestração multi-agente
- **Google Gemini** — API LLM (free tier)
- **Supabase** — Hospedagem PostgreSQL (free tier)
- Comunidades **FastAPI** & **Streamlit**
- Tradução bíblica: Nova Almeida Atualizada (NAA)

---

<div align="center">

**Construído com LangGraph · FastAPI · Streamlit · Google Gemini**

</div>
