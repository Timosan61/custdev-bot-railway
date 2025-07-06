#!/usr/bin/env python3
"""
Start the API server for n8n integration.
This server provides HTTP endpoints for LLM operations.
"""

import os
import sys
import uvicorn
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Start the API server"""
    # Check if API is enabled
    api_enabled = os.getenv("API_ENABLED", "false").lower() == "true"
    
    if not api_enabled:
        logger.error("API is not enabled. Set API_ENABLED=true in .env file")
        sys.exit(1)
    
    # Get configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    # Check required configuration
    if not os.getenv("API_SECRET_KEY"):
        logger.error("API_SECRET_KEY not set in .env file")
        sys.exit(1)
    
    # Log startup info
    logger.info(f"Starting API server on {host}:{port}")
    logger.info("Press Ctrl+C to stop")
    
    # Run the server
    try:
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            reload=False,  # Disable reload in production
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("API server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()