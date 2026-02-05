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
