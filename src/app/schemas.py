from pydantic import BaseModel, field_validator
from typing import List


class VerseResponse(BaseModel):
    number: int
    text: str


class AnalyzeRequest(BaseModel):
    book: str
    chapter: int
    verses: List[int]
    selected_modules: List[str]

    @field_validator("selected_modules")
    @classmethod
    def validate_modules(cls, v):
        valid_modules = {"panorama", "exegese", "teologia"}
        if not v:
            raise ValueError("At least one module must be selected")
        for module in v:
            if module not in valid_modules:
                raise ValueError(f"Invalid module: {module}. Valid: {valid_modules}")
        return v

    @field_validator("verses")
    @classmethod
    def validate_verses(cls, v):
        if not v:
            raise ValueError("At least one verse must be selected")
        return v


class AnalyzeResponse(BaseModel):
    final_analysis: str
