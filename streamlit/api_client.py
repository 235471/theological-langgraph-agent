import requests
import os
import sys

# Garante que a pasta 'src' está no PATH para o Direct-Call (Modo Cloud)
try:
    src_path = os.path.join(os.getcwd(), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
except Exception:
    pass


class APIClient:
    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.timeout = 180  # Increased for multi-agent execution

    def get_verses(self, abbrev: str, chapter: int):
        try:
            response = requests.get(
                f"{self.base_url}/bible/{abbrev}/{chapter}/verses", timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            # Fallback para execução direta (Streamlit Cloud)
            try:
                from app.service.bible_service import get_verses

                return get_verses(abbrev, chapter)
            except Exception as e:
                print(f"Erro no modo Direct-Call (get_verses): {e}")
                return []

    def analyze(self, payload: dict) -> dict:
        """
        Call the analysis endpoint.

        Returns a dict with:
            - final_analysis: str
            - from_cache: bool
            - run_id: str | None
            - tokens_consumed: dict | None
            - model_versions: dict | None
            - risk_level: str | None
            - hitl_status: str | None
        """
        default_result = {
            "final_analysis": "",
            "from_cache": False,
            "run_id": None,
            "tokens_consumed": None,
            "model_versions": None,
            "risk_level": None,
            "hitl_status": None,
        }

        try:
            # Tenta API primeiro
            response = requests.post(
                f"{self.base_url}/analyze", json=payload, timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return {**default_result, **data}
            else:
                error_detail = response.json().get("detail", response.text)
                return {**default_result, "final_analysis": f"Erro: {error_detail}"}
        except requests.exceptions.ConnectionError:
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
                    return {
                        "final_analysis": result.final_analysis,
                        "from_cache": result.from_cache,
                        "run_id": result.run_id,
                        "tokens_consumed": result.tokens_consumed,
                        "model_versions": result.model_versions,
                        "risk_level": result.risk_level,
                        "hitl_status": result.hitl_status,
                    }
                return {
                    **default_result,
                    "final_analysis": f"Erro na análise: {result.error}",
                }
            except Exception as e:
                import traceback

                print(traceback.format_exc())
                return {**default_result, "final_analysis": f"Erro: {str(e)}"}
        except Exception as e:
            return {**default_result, "final_analysis": f"Erro: {str(e)}"}

    def get_hitl_pending(self) -> list:
        """Get pending HITL reviews."""
        try:
            response = requests.get(f"{self.base_url}/hitl/pending", timeout=5)
            if response.status_code == 200:
                return response.json().get("pending", [])
        except Exception:
            pass
        return []


api_client = APIClient()
