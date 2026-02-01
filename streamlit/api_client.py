import requests
import os
import sys

# Tenta adicionar o diretório 'src' ao path para permitir imports diretos no Streamlit Cloud
try:
    sys.path.append(os.path.join(os.getcwd(), "src"))
except:
    pass


class APIClient:
    def __init__(self):
        # Em desenvolvimento local, usa o endereço do FastAPI
        # No Streamlit Cloud, podemos sobrescrever isso via Secrets
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.timeout = 120

    def get_verses(self, abbrev: str, chapter: int):
        """Tenta buscar via API, se falhar tenta carregar localmente (Modo Cloud)."""
        try:
            response = requests.get(
                f"{self.base_url}/bible/{abbrev}/{chapter}/verses", timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except:
            # Se a API falhar (não está rodando), tentamos usar o serviço diretamente
            # Isso permite que o Streamlit Cloud funcione sem um backend FastAPI separado
            try:
                from app.service.bible_service import get_verses

                return get_verses(abbrev, chapter)
            except Exception as e:
                print(f"Erro no modo Direct-Call: {e}")
                return []

    def analyze(self, payload: dict):
        """Tenta enviar para a API, se falhar executa o agente localmente."""
        try:
            response = requests.post(
                f"{self.base_url}/analyze", json=payload, timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json().get("final_analysis", "")
        except:
            # Modo Direct-Call (Invocação direta do Agente no mesmo processo do Streamlit)
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
                return f"Erro ao tentar executar agente sem backend: {str(e)}"


api_client = APIClient()
