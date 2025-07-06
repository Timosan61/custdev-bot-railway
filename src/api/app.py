from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os
from loguru import logger

from src.api.endpoints import router


# Security
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify API key for authentication"""
    api_key = os.getenv("API_SECRET_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    if credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return credentials.credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    logger.info("Starting API server for n8n integration...")
    yield
    logger.info("Shutting down API server...")


# Create FastAPI app
app = FastAPI(
    title="CustDev Bot API",
    description="API endpoints for n8n integration with CustDev Bot",
    version="1.0.0",
    lifespan=lifespan
)

# Include routes with authentication
app.include_router(
    router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)]
)

# Health check endpoint (no auth required)
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "custdev-bot-api"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "CustDev Bot API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "api": "/api/v1",
            "docs": "/docs"
        }
    }