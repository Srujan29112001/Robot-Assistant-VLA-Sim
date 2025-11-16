"""
Main FastAPI application
Implements REST API and MCP server for robotic assistant
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn
from contextlib import asynccontextmanager
import logging
from typing import Optional

from api.routes import commands, state, mcp_server, voice, graphql_api_integrated
from api.models.schemas import HealthCheck
from api.utils.config import settings
from api.utils.database import init_databases, close_databases

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Vision-Language Robotic Assistant API...")
    await init_databases()
    logger.info("Databases initialized")

    # Initialize voice services
    try:
        voice.initialize_voice_services()
        logger.info("Voice services initialized")
    except Exception as e:
        logger.warning(f"Voice services initialization failed: {e}")

    yield
    # Shutdown
    logger.info("Shutting down API...")
    await close_databases()
    logger.info("Databases closed")


# Create FastAPI app
app = FastAPI(
    title="Vision-Language Robotic Assistant API",
    description="Embodied AI system for robotic assistants with vision-language understanding",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Include routers
app.include_router(commands.router, prefix="/api/v1", tags=["commands"])
app.include_router(state.router, prefix="/api/v1", tags=["state"])
app.include_router(mcp_server.router, prefix="/mcp", tags=["mcp"])
app.include_router(voice.router, prefix="/api/v1", tags=["voice"])
app.include_router(graphql_api_integrated.router, prefix="/graphql", tags=["graphql"])


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "Vision-Language Robotic Assistant",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        version="0.1.0",
        services={
            "api": "operational",
            "mcp": "operational",
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred"}
    )


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
