from typing import List
from pydantic import BaseModel, Field


class AnalysisOutput(BaseModel):
    """Schema for structured LLM output. Expects clean markdown text."""

    content: str = Field(
        description=(
            "O conteúdo completo da análise em formato Markdown. "
            "Use quebras de linha reais (não \\n escapado). "
            "Não retorne JSON - apenas o texto markdown puro."
        )
    )


class ValidatorOutput(BaseModel):
    """Schema for the theological validator structured output."""

    content: str = Field(
        description=(
            "O conteúdo completo da validação teológica em formato Markdown. "
            "Use quebras de linha reais (não \\n escapado). "
            "Não retorne JSON - apenas o texto markdown puro."
        )
    )
    risk_level: str = Field(
        description=(
            "Nível de risco teológico identificado: 'low', 'medium' ou 'high'. "
            "Use 'high' apenas para desvios graves de ortodoxia, erros exegéticos "
            "críticos ou interpretações que violem princípios fundamentais."
        )
    )
    alerts: List[str] = Field(
        default_factory=list,
        description=(
            "Lista de alertas teológicos identificados. "
            "Apenas alertas que justifiquem o risk_level atribuído. "
            "Deixe vazia se risk_level for 'low'."
        ),
    )
