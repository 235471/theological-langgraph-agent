from pydantic import BaseModel, Field

class AnalysisOutput(BaseModel):
    content: str = Field(description="O conteúdo da análise em markdown")
    key_points: list[str] = Field(description="Pontos chave identificados")
