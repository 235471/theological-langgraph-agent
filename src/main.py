import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables for LangSmith and API Keys
load_dotenv()

from app.controller.bible_controller import router as bible_router
from app.controller.analyze_controller import router as analyze_router
from app.controller.debug_controller import router as debug_router

app = FastAPI(
    title="Theological Agent API",
    description="API backend for the multi-agent theological analysis system.",
    version="1.0.0",
)

# CORS Middleware (allow Streamlit frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bible_router)
app.include_router(analyze_router)
app.include_router(debug_router)


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Theological Agent API is running"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
