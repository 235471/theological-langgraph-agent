"""
Debug Controller - Endpoints for testing and debugging
"""

import logging
from fastapi import APIRouter
from app.client.client import get_panorama_model

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/test-llm")
async def test_llm():
    """Test if LLM client can be instantiated and called."""
    try:
        from langchain_core.messages import HumanMessage

        model = get_panorama_model()
        response = model.invoke([HumanMessage(content="Say 'hello' in one word.")])

        return {
            "status": "success",
            "response": response.content,
            "model_used": "gemini-2.5-flash (FLASH tier)",
        }
    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"LLM Test failed: {e}")
        logger.error(error_trace)
        return {"status": "error", "error": str(e), "traceback": error_trace}


@router.get("/test-env")
async def test_env():
    """Check if environment variables are loaded."""
    import os

    return {
        "GOOGLE_API_KEY": (
            "***" + os.getenv("GOOGLE_API_KEY", "NOT_FOUND")[-4:]
            if os.getenv("GOOGLE_API_KEY")
            else "NOT_FOUND"
        ),
        "LANGSMITH_API_KEY": "SET" if os.getenv("LANGSMITH_API_KEY") else "NOT_SET",
        "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2", "NOT_SET"),
    }


@router.get("/test-agent")
async def test_agent():
    """Test the full LangGraph agent execution."""
    try:
        from app.service.analysis_service import run_analysis, AnalysisInput

        # Minimal test case
        test_input = AnalysisInput(
            book="Sl",
            chapter=23,
            verses=[1],
            selected_modules=["panorama"],  # Only one module to minimize API calls
        )

        logger.info("Starting agent test...")
        result = run_analysis(test_input)

        if result.success:
            return {
                "status": "success",
                "analysis_preview": (
                    result.final_analysis[:200] + "..."
                    if len(result.final_analysis) > 200
                    else result.final_analysis
                ),
            }
        else:
            return {"status": "failed", "error": result.error}

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"Agent test failed: {e}")
        logger.error(error_trace)
        return {"status": "error", "error": str(e), "traceback": error_trace}
