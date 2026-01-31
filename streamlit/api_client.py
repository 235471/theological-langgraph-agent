import os
import requests
from typing import List, Dict, Optional

# Backend API URL - can be overridden via environment variable
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


class ApiClient:
    """Client for communicating with the Theological Agent API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.timeout = 120  # 2 minutes timeout for agent processing

    def get_verses(self, book_abbrev: str, chapter: int) -> List[Dict]:
        """
        Fetch verses for a specific book and chapter.

        GET /bible/{abbrev}/{chapter}/verses

        Returns:
            List of dicts: [{'number': int, 'text': str}, ...]
        """
        try:
            url = f"{self.base_url}/bible/{book_abbrev}/{chapter}/verses"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[API Error] get_verses failed: {e}")
            # Return empty list on error to gracefully handle UI
            return []

    def analyze(self, payload: Dict) -> str:
        """
        Send analysis request to the agent.

        POST /analyze

        Payload: {
            "book": str,
            "chapter": int,
            "verses": List[int],
            "selected_modules": List[str]
        }

        Returns:
            Markdown string with the analysis result.
        """
        try:
            url = f"{self.base_url}/analyze"
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get("final_analysis", "Análise não disponível.")
        except requests.exceptions.Timeout:
            return (
                "❌ **Erro**: O tempo limite da análise foi excedido. Tente novamente."
            )
        except requests.exceptions.RequestException as e:
            return f"❌ **Erro de conexão**: {str(e)}"
        except Exception as e:
            return f"❌ **Erro inesperado**: {str(e)}"


# Singleton instance for easy import
api_client = ApiClient()
