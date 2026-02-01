import requests
import os
import sys

# Garante que a pasta 'src' está no PATH para o Direct-Call (Modo Cloud)
# Usamos o caminho absoluto para evitar ambiguidades
try:
    src_path = os.path.join(os.getcwd(), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)  # Insere no início para ter prioridade
except:
    pass


class APIClient:
    def __init__(self):
        # Em desenvolvimento local, usa o endereço do FastAPI
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.timeout = 120

    def get_verses(self, abbrev: str, chapter: int):
        try:
            # Tenta API primeiro
            response = requests.get(
                f"{self.base_url}/bible/{abbrev}/{chapter}/verses", timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except:
            # Fallback para execução direta (Streamlit Cloud)
            try:
                from app.service.bible_service import get_verses

                return get_verses(abbrev, chapter)
            except Exception as e:
                print(f"Erro no modo Direct-Call (get_verses): {e}")
                return []

    def analyze(self, payload: dict):
        try:
            # Tenta API primeiro
            response = requests.post(
                f"{self.base_url}/analyze", json=payload, timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json().get("final_analysis", "")
        except:
            # Fallback para execução direta (Streamlit Cloud)
            try:
                from app.service.analysis_service import run_analysis, AnalysisInput

                input_data = AnalysisInput(
                    book=payload["book"],
                    chapter=payload["chapter"],
                    verses=payload["verses"],
                    selected_modules=payload["selected_modules"],
                )

                result = run_analysis(input_data)
                if result.success:
                    return result.final_analysis
                return f"Erro na análise direta: {result.error}"
            except Exception as e:
                import traceback

                print(traceback.format_exc())
                return f"Erro ao tentar executar agente sem backend: {str(e)}"


api_client = APIClient()
