import json
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
        self.timeout = 600  # Increased to 10 minutes for deep analysis chains

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
                try:
                    from app.service.trace_service import export_graph_trace
                except Exception:
                    export_graph_trace = None

                input_data = AnalysisInput(
                    book=payload["book"],
                    chapter=payload["chapter"],
                    verses=payload["verses"],
                    selected_modules=payload["selected_modules"],
                )

                result = run_analysis(input_data)
                if (
                    export_graph_trace
                    and not result.from_cache
                    and result.run_id
                    and result.langsmith_run_id
                ):
                    try:
                        export_graph_trace(result.run_id, result.langsmith_run_id)
                    except Exception as trace_err:
                        print(f"Direct-call trace export failed: {trace_err}")

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

    def stream_analyze(self, payload: dict):
        """
        Streaming version of analyze().

        Calls POST /analyze/stream and yields parsed event dicts as they arrive.
        Falls back to _stream_direct() if no API server is reachable
        (e.g. Streamlit Cloud direct-call mode).

        Event dicts have an "event" key:
          "cache_hit"    – served from cache; includes final_analysis
          "stage_start"  – entering stage 1/2/3
          "node_complete"– a graph node finished
          "complete"     – graph done; includes final result fields
          "error"        – unrecoverable failure
        """
        try:
            response = requests.post(
                f"{self.base_url}/analyze/stream",
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            response.raise_for_status()
            for raw_line in response.iter_lines():
                if raw_line:
                    try:
                        yield json.loads(raw_line)
                    except json.JSONDecodeError:
                        pass  # skip malformed lines
        except requests.exceptions.ConnectionError:
            # No API server — run directly (Streamlit Cloud)
            yield from self._stream_direct(payload)
        except Exception as e:
            yield {"event": "error", "error": str(e)}

    def _stream_direct(self, payload: dict):
        """Direct-call fallback for when no API server is running."""
        try:
            from app.service.analysis_service import stream_analysis, AnalysisInput

            input_data = AnalysisInput(
                book=payload["book"],
                chapter=payload["chapter"],
                verses=payload["verses"],
                selected_modules=payload["selected_modules"],
            )
            yield from stream_analysis(input_data)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            yield {"event": "error", "error": str(e)}

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
