"""
SafeSim FastAPI REST API
Provides programmatic access to SafeSim medical text simplification
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
load_dotenv()

from src.safesim_pipeline import SafeSimPipeline, SafeSimResult

# Initialize FastAPI app
app = FastAPI(
    title="SafeSim API",
    description="Safe Medical Text Simplification API with Guaranteed Fact Preservation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class SimplificationRequest(BaseModel):
    text: str = Field(..., description="Medical text to simplify", min_length=1)
    llm_backend: str = Field(default="dummy", description="LLM backend: 'dummy', 'openai', 'claude', 'huggingface'")
    strictness: str = Field(default="high", description="Verification strictness: 'high', 'medium', 'low'")
    api_key: Optional[str] = Field(default=None, description="API key for LLM backend (optional if set in env)")
    verbose: bool = Field(default=False, description="Return verbose output")


class EntityResponse(BaseModel):
    text: str
    type: str
    start: int
    end: int


class VerificationResponse(BaseModel):
    is_safe: bool
    score: float
    missing_entities: List[str]
    warnings: List[str]


class SimplificationResponse(BaseModel):
    original_text: str
    simplified_text: str
    entities: List[EntityResponse]
    verification: VerificationResponse
    is_safe: bool
    is_relevant: bool
    relevance_status: str
    relevance_explanation: str
    warnings: List[str]
    model_used: str


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "SafeSim API",
        "version": "1.0.0",
        "description": "Safe Medical Text Simplification API",
        "endpoints": {
            "docs": "/api/docs",
            "health": "/api/health",
            "simplify": "/api/simplify"
        }
    }


@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "SafeSim API"}


@app.post("/api/simplify", response_model=SimplificationResponse)
async def simplify_text(request: SimplificationRequest):
    """
    Simplify medical text while preserving critical facts.
    
    This endpoint processes medical text through the SafeSim pipeline:
    1. Extracts critical medical entities (medications, dosages, vitals)
    2. Simplifies text using LLM
    3. Verifies that all critical entities are preserved
    4. Returns simplified text with safety verification
    """
    try:
        # Initialize pipeline
        kwargs = {}
        if request.api_key:
            kwargs['api_key'] = request.api_key
        elif request.llm_backend == "openai":
            kwargs['api_key'] = os.getenv("OPENAI_API_KEY")
        elif request.llm_backend == "claude":
            kwargs['api_key'] = os.getenv("ANTHROPIC_API_KEY")
        
        pipeline = SafeSimPipeline(
            llm_backend=request.llm_backend,
            strictness=request.strictness,
            **kwargs
        )
        
        # Process text
        result: SafeSimResult = pipeline.process(request.text, verbose=request.verbose)
        
        # Convert entities to response format
        entities = [
            EntityResponse(
                text=e['text'],
                type=e['type'],
                start=e['start'],
                end=e['end']
            )
            for e in result.entities
        ]
        
        # Convert verification to response format
        verification = VerificationResponse(
            is_safe=result.verification.get('is_safe', False),
            score=result.verification.get('score', 0.0),
            missing_entities=result.verification.get('missing_entities', []),
            warnings=result.verification.get('warnings', [])
        )
        
        # Build response
        response = SimplificationResponse(
            original_text=result.original_text,
            simplified_text=result.simplified_text,
            entities=entities,
            verification=verification,
            is_safe=result.is_safe,
            is_relevant=result.is_relevant,
            relevance_status=result.relevance_status,
            relevance_explanation=result.relevance_explanation,
            warnings=result.warnings,
            model_used=result.model_used
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing text: {str(e)}")


@app.get("/api/backends")
async def list_backends():
    """List available LLM backends"""
    return {
        "backends": [
            {
                "name": "dummy",
                "description": "Rule-based simplification (no API key required)",
                "requires_api_key": False
            },
            {
                "name": "openai",
                "description": "OpenAI GPT models",
                "requires_api_key": True
            },
            {
                "name": "claude",
                "description": "Anthropic Claude models",
                "requires_api_key": True
            },
            {
                "name": "huggingface",
                "description": "HuggingFace transformers",
                "requires_api_key": False
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

