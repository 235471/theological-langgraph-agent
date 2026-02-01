import streamlit as st
from bible_books import BOOKS
from api_client import api_client
import time

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
    st.session_state.chapter_data = []  # List of verses for current chapter
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""
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
        # Reset selection when chapter changes? Usually yes.
        st.session_state.selected_verses_ids = []


def run_analysis():
    """Triggers the agent analysis."""
    st.session_state.is_analyzing = True

    # Construct Payload
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
        modules = ["panorama", "exegese", "teologia"]  # Full mode

    payload = {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "selected_modules": modules,
    }

    # Call API
    result = api_client.analyze(payload)
    st.session_state.analysis_result = result
    st.session_state.is_analyzing = False


# --- TOP CONTROL BAR ---
with st.container():
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1.5])

    # Col 1: Book Selection
    # Format options for display, but keep keys for logic
    book_options = list(BOOKS.keys())

    def format_book_func(abbrev):
        return BOOKS[abbrev]["name"]

    selected_book_abbrev = col1.selectbox(
        "Livro",
        options=book_options,
        format_func=format_book_func,
        key="selected_book_abbrev",
        on_change=fetch_chapter_data,
        # Note: on_change might trigger before chapter updates if not careful,
        # but since chapter defaults to 1 or stays, we handle it.
    )

    # Col 2: Mode Selection
    mode = col2.radio(
        "Modo de Análise", ["Full", "Custom"], horizontal=True, key="mode"
    )

    # Col 3: Modules (Conditional)
    if mode == "Custom":
        c3_1, c3_2, c3_3 = col3.columns(3)
        c3_1.checkbox("Panorama", key="mod_panorama")
        c3_2.checkbox("Exegese", key="mod_exegese")
        c3_3.checkbox("Teologia", key="mod_teologia")
    else:
        col3.info("Todos os módulos serão executados.")

    # Col 4: Analyze Button
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
    # 1. Chapter Selection
    # Get max chapters for selected book
    max_chapters = BOOKS[selected_book_abbrev]["chapters"]

    # Simple horizontal number input or selectbox.
    # For a "Pills" look we might use a horizontal radio if few chapters,
    # but for 50+ chapters, a number_input or selectbox is better UX.
    selected_chapter = st.number_input(
        f"Capítulo (1-{max_chapters})",
        min_value=1,
        max_value=max_chapters,
        value=1,
        key="selected_chapter",
        on_change=fetch_chapter_data,
    )

    st.markdown(f"### {BOOKS[selected_book_abbrev]['name']} {selected_chapter}")

    # Ensure data is loaded (handle first load)
    if not st.session_state.chapter_data:
        fetch_chapter_data()

    # 2. Verse Selection
    st.write("Selecione os versículos:")

    if st.session_state.chapter_data:
        # Select All Toggle
        if st.checkbox("Selecionar Todos"):
            st.session_state.selected_verses_ids = [
                v["number"] for v in st.session_state.chapter_data
            ]

        # Native scrollable container for verses
        current_selection = []
        with st.container(height=500):
            for verse in st.session_state.chapter_data:
                v_num = verse["number"]
                v_text = verse["text"]

                # Check if this verse is currently in our managed list
                is_checked = v_num in st.session_state.selected_verses_ids

                # Display: Checkbox + Text
                v_col1, v_col2 = st.columns([0.15, 0.85])
                if v_col1.checkbox(f"{v_num}", value=is_checked, key=f"v_{v_num}"):
                    current_selection.append(v_num)

                v_col2.caption(f"**{v_num}** {v_text}")

        # Update state
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
        # Wrap result in a styled container using standard HTML/CSS injection
        combined_html = f"""
        <div class="agent-result-container">
            {st.session_state.analysis_result}
        </div>
        """
        st.markdown(combined_html, unsafe_allow_html=True)

        # Copy Button Workaround: Streamlit native code block has a copy button
        with st.expander("📋 Copiar Texto (Formato Markdown)"):
            st.code(st.session_state.analysis_result, language="markdown")
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
