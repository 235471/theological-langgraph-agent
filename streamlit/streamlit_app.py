import streamlit as st
import os
from dotenv import load_dotenv
from bible_books import BOOKS
from api_client import api_client
import time

# --- Environment & Tracing Setup ---
load_dotenv()

if "LANGCHAIN_TRACING_V2" in st.secrets:
    for key, value in st.secrets.items():
        if (
            key.startswith("LANGCHAIN_")
            or key == "GOOGLE_API_KEY"
            or key == "LANGSMITH_API_KEY"
        ):
            os.environ[key] = str(value)

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
    st.session_state.analysis_result = None  # Now stores full dict
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False
if "selected_verses_ids" not in st.session_state:
    st.session_state.selected_verses_ids = []


# --- Helper Functions ---
def fetch_chapter_data():
    """Fetches verses when book or chapter changes."""
    book = st.session_state.get("selected_book_abbrev")
    chapter = st.session_state.get("selected_chapter")
    if book and chapter:
        verses = api_client.get_verses(book, chapter)
        st.session_state.chapter_data = verses
        st.session_state.selected_verses_ids = []


def run_analysis():
    """Triggers the agent analysis."""
    st.session_state.is_analyzing = True

    book = st.session_state.selected_book_abbrev
    chapter = st.session_state.selected_chapter
    verses = st.session_state.selected_verses_ids

    mode = st.session_state.mode
    modules = []
    if mode == "Custom":
        if st.session_state.get("mod_panorama"):
            modules.append("panorama")
        if st.session_state.get("mod_exegese"):
            modules.append("exegese")
        if st.session_state.get("mod_teologia"):
            modules.append("teologia")
    else:
        modules = ["panorama", "exegese", "teologia"]

    payload = {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "selected_modules": modules,
    }

    # Returns dict with governance metadata
    result = api_client.analyze(payload)
    st.session_state.analysis_result = result
    st.session_state.is_analyzing = False


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
        c3_3.checkbox("Teologia", key="mod_teologia")
    else:
        col3.info("Todos os módulos serão executados.")

    analyze_clicked = col4.button(
        "Analyze ✨",
        type="primary",
        on_click=run_analysis,
        disabled=st.session_state.is_analyzing
        or not st.session_state.selected_verses_ids,
    )

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
        if st.checkbox("Selecionar Todos"):
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

# --- RIGHT PANEL: Analysis Results ---
with right_panel:
    if st.session_state.is_analyzing:
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; height: 300px;">
                <h3>🤖 O Agente está analisando as Escrituras...</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
            combined_html = f"""
            <div class="agent-result-container">
                {final_text}
            </div>
            """
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
