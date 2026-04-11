import streamlit as st
import os
from dotenv import load_dotenv
from bible_books import BOOKS
from api_client import api_client
import time

# --- Environment & Tracing Setup ---
load_dotenv()

try:
    if "LANGCHAIN_TRACING_V2" in st.secrets:
        for key, value in st.secrets.items():
            if (
                key.startswith("LANGCHAIN_")
                or key == "GOOGLE_API_KEY"
                or key == "LANGSMITH_API_KEY"
            ):
                os.environ[key] = str(value)
except Exception:
    pass  # No secrets.toml — running locally with .env

# --- Page Configuration ---
st.set_page_config(
    page_title="Agente Teológico",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- CSS Injection ---
with open("streamlit/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- State Initialization ---
if "chapter_data" not in st.session_state:
    st.session_state.chapter_data = []
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False
if "selected_verses_ids" not in st.session_state:
    st.session_state.selected_verses_ids = []
if "do_analysis" not in st.session_state:
    st.session_state.do_analysis = False


# --- Helper Functions ---
def fetch_chapter_data():
    """Fetches verses when book or chapter changes."""
    book = st.session_state.get("selected_book_abbrev")
    chapter = st.session_state.get("selected_chapter")
    if book and chapter:
        verses = api_client.get_verses(book, chapter)
        st.session_state.chapter_data = verses
        st.session_state.selected_verses_ids = []


def _build_payload():
    """Build the analysis payload from current widget state."""
    book = st.session_state.selected_book_abbrev
    chapter = st.session_state.selected_chapter

    verses = []
    if st.session_state.get("select_all_verses"):
        verses = [v["number"] for v in st.session_state.get("chapter_data", [])]
    else:
        for v in st.session_state.get("chapter_data", []):
            if st.session_state.get(f"v_{v['number']}"):
                verses.append(v["number"])

    mode = st.session_state.mode
    modules = []
    if mode == "Custom":
        if st.session_state.get("mod_panorama"):
            modules.append("panorama")
        if st.session_state.get("mod_exegese"):
            modules.append("exegese")
        if st.session_state.get("mod_historica"):
            modules.append("historical")
    else:
        modules = ["panorama", "exegese", "historical"]

    return {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "selected_modules": modules,
    }


# ─── Labels for the streaming progress display ───────────────────────────────
_STAGE_HEADINGS = {
    1: "🔍 Estágio 1 — Análise Multi-Agente",
    2: "⚖️ Estágio 2 — Validação Teológica",
    3: "📝 Estágio 3 — Síntese do Estudo",
}
_NODE_LABELS = {
    "panorama_agent":        "Panorama Bíblico",
    "lexical_agent":         "Exegese Lexical (ADK)",
    "historical_agent":      "Contexto Histórico",
    "intertextual_agent":    "Análise Intertextual",
    "theological_validator": "Validador Teológico",
    "hitl_pending":          "Revisão Humana Requerida",
    "synthesizer":           "Sintetizando estudo...",
}


# --- TOP CONTROL BAR ---
with st.container():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1.5])

    book_options = list(BOOKS.keys())

    def format_book_func(abbrev):
        return BOOKS[abbrev]["name"]

    selected_book_abbrev = col1.selectbox(
        "Livro",
        options=book_options,
        format_func=format_book_func,
        key="selected_book_abbrev",
        on_change=fetch_chapter_data,
    )

    mode = col2.radio(
        "Modo de Análise", ["Full", "Custom"], horizontal=True, key="mode"
    )

    if mode == "Custom":
        c3_1, c3_2, c3_3 = col3.columns(3)
        c3_1.checkbox("Panorama", key="mod_panorama")
        c3_2.checkbox("Exegese", key="mod_exegese")
        c3_3.checkbox("Histórica", key="mod_historica")
    else:
        col3.info("Todos os módulos serão executados.")

    # Determine if any verses are currently selected based on widget states
    has_selection = False
    if st.session_state.get("select_all_verses"):
        has_selection = True
    elif st.session_state.get("chapter_data"):
        has_selection = any(
            st.session_state.get(f"v_{v['number']}")
            for v in st.session_state.chapter_data
        )

    # Button sets a flag; analysis runs in the main render path below so that
    # st.status() can update live (on_click callbacks buffer all UI writes and
    # only render them after the callback returns — incompatible with streaming).
    if col4.button(
        "Analyze ✨",
        type="primary",
        disabled=st.session_state.is_analyzing or not has_selection,
    ):
        st.session_state.do_analysis = True
        st.session_state.analysis_result = None  # clear previous result

st.divider()

# --- MAIN SPLIT LAYOUT ---
left_panel, right_panel = st.columns([1, 2])

# --- LEFT PANEL: Context & Verses ---
with left_panel:
    max_chapters = BOOKS[selected_book_abbrev]["chapters"]

    selected_chapter = st.number_input(
        f"Capítulo (1-{max_chapters})",
        min_value=1,
        max_value=max_chapters,
        value=1,
        key="selected_chapter",
        on_change=fetch_chapter_data,
    )

    st.markdown(f"### {BOOKS[selected_book_abbrev]['name']} {selected_chapter}")

    if not st.session_state.chapter_data:
        fetch_chapter_data()

    st.write("Selecione os versículos:")

    if st.session_state.chapter_data:
        select_all = st.checkbox("Selecionar Todos", key="select_all_verses")
        if select_all:
            st.session_state.selected_verses_ids = [
                v["number"] for v in st.session_state.chapter_data
            ]

        current_selection = []
        with st.container(height=500):
            for verse in st.session_state.chapter_data:
                v_num = verse["number"]
                v_text = verse["text"]

                is_checked = v_num in st.session_state.selected_verses_ids

                v_col1, v_col2 = st.columns([0.15, 0.85])
                if v_col1.checkbox(f"{v_num}", value=is_checked, key=f"v_{v_num}"):
                    current_selection.append(v_num)

                v_col2.caption(f"**{v_num}** {v_text}")

        st.session_state.selected_verses_ids = current_selection

    else:
        st.spinner("Carregando versículos...")

# --- RIGHT PANEL: Analysis / Streaming Progress / Results ---
with right_panel:

    # ── Streaming Analysis (main render path — required for live st.status) ──
    if st.session_state.get("do_analysis") and not st.session_state.is_analyzing:
        st.session_state.do_analysis = False
        st.session_state.is_analyzing = True

        payload = _build_payload()
        result = None
        seen_stages: set = set()

        with st.status("📖 Analisando Escrituras...", expanded=True) as status:
            start_ts = time.time()

            for event in api_client.stream_analyze(payload):
                etype = event.get("event")

                if etype == "cache_hit":
                    status.update(label="⚡ Resultado do Cache!", state="complete")
                    result = event
                    break

                elif etype == "stage_start":
                    stage = event.get("stage", 1)
                    if stage not in seen_stages:
                        seen_stages.add(stage)
                        st.write(f"**{_STAGE_HEADINGS.get(stage, '')}**")

                elif etype == "node_complete":
                    node = event.get("node")
                    stage = event.get("stage", 1)

                    # Emit stage heading when we see the first node of a new stage
                    # (covers the rare case the backend emits node before stage_start)
                    if stage not in seen_stages:
                        seen_stages.add(stage)
                        st.write(f"**{_STAGE_HEADINGS.get(stage, '')}**")

                    # Skip internal sync node (it's invisible to the user)
                    if node not in ("join",):
                        elapsed = int(time.time() - start_ts)
                        label = _NODE_LABELS.get(node, node)
                        st.write(f"  ✅ {label} _({elapsed}s)_")

                elif etype == "complete":
                    elapsed = int(time.time() - start_ts)
                    status.update(
                        label=f"✅ Análise concluída! ({elapsed}s)",
                        state="complete",
                    )
                    result = event

                elif etype == "error":
                    status.update(label="❌ Erro na análise", state="error")
                    result = {
                        "final_analysis": f"❌ Erro: {event.get('error', 'Desconhecido')}",
                        "from_cache": False,
                    }

        st.session_state.analysis_result = result
        st.session_state.is_analyzing = False
        st.rerun()  # Re-render to display the result in the results panel below

    # ─── Results Panel ────────────────────────────────────────────────────────
    elif st.session_state.analysis_result:
        result = st.session_state.analysis_result
        final_text = (
            result.get("final_analysis", "") if isinstance(result, dict) else result
        )

        # --- Status Badges ---
        badge_cols = st.columns(4)

        # Cache badge
        if isinstance(result, dict) and result.get("from_cache"):
            badge_cols[0].success("🔄 Cache Hit")
        elif isinstance(result, dict) and result.get("run_id"):
            badge_cols[0].info("🆕 Nova Análise")

        # Risk level badge
        if isinstance(result, dict) and result.get("risk_level"):
            risk = result["risk_level"]
            if risk == "high":
                badge_cols[1].error(f"⚠️ Risco: {risk.upper()}")
            elif risk == "medium":
                badge_cols[1].warning(f"🔶 Risco: {risk.upper()}")
            else:
                badge_cols[1].success(f"✅ Risco: {risk.upper()}")

        # HITL status
        if isinstance(result, dict) and result.get("hitl_status"):
            hitl = result["hitl_status"]
            if hitl == "pending":
                badge_cols[2].error("🛑 HITL: Pendente")
            elif hitl == "approved":
                badge_cols[2].success("✅ HITL: Aprovado")
            elif hitl == "edited":
                badge_cols[2].info("✏️ HITL: Editado")

        # Run ID
        if isinstance(result, dict) and result.get("run_id"):
            badge_cols[3].caption(f"🆔 `{result['run_id'][:8]}`")

        # --- Main Content ---
        if final_text:
            combined_html = f'<div class="agent-result-container">\n\n{final_text}\n\n</div>'
            st.markdown(combined_html, unsafe_allow_html=True)

            with st.expander("📋 Copiar Texto (Formato Markdown)"):
                st.code(final_text, language="markdown")

        # --- Governance Metadata Panel ---
        if isinstance(result, dict) and (
            result.get("tokens_consumed") or result.get("model_versions")
        ):
            with st.expander("📊 Metadados de Governança"):
                meta_cols = st.columns(2)

                # Token consumption
                if result.get("tokens_consumed"):
                    with meta_cols[0]:
                        st.markdown("**Tokens Consumidos:**")
                        tokens = result["tokens_consumed"]
                        total_in = 0
                        total_out = 0
                        for node_name, usage in tokens.items():
                            if isinstance(usage, dict):
                                inp = usage.get("input", 0)
                                out = usage.get("output", 0)
                                total_in += inp
                                total_out += out
                                st.caption(f"`{node_name}`: {inp} in / {out} out")
                        st.markdown(
                            f"**Total: {total_in} in / {total_out} out = {total_in + total_out}**"
                        )

                # Model versions
                if result.get("model_versions"):
                    with meta_cols[1]:
                        st.markdown("**Modelos Utilizados:**")
                        models = result["model_versions"]
                        for node_name, model in models.items():
                            st.caption(f"`{node_name}`: {model}")

    else:
        # Empty State
        st.markdown(
            """
            <div style="
                border: 2px dashed #31333F;
                border-radius: 10px;
                height: 500px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                color: #888;">
                <h3>Aguardando Análise</h3>
                <p>Selecione um texto e clique em "Analyze" para começar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
