from typing import List, Literal
from pydantic import BaseModel, Field


class AnalysisOutput(BaseModel):
    """Schema for structured LLM output. Expects clean markdown text."""

    content: str = Field(
        min_length=300,
        description="O conteúdo completo da análise em formato Markdown. Use quebras de linha reais entre parágrafos. Desenvolva cada seção com profundidade.",
    )


class ValidatorOutput(BaseModel):
    """Schema for the theological validator structured output."""

    content: str = Field(
        min_length=300,
        description="O conteúdo completo da validação teológica em formato Markdown. Inclua análise dos testes obrigatórios e nível de confiança por conclusão.",
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Nível de risco teológico identificado. Use 'high' apenas para desvios graves de ortodoxia, erros exegéticos críticos ou incoerência teológica séria."
    )
    alerts: List[str] = Field(
        default_factory=list,
        description="Lista de alertas que sustentam o risk_level. Deixe vazia quando risk_level for 'low'.",
    )
