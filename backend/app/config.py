"""
Environment Configuration Loader and Validator

This module provides utilities for loading and validating environment variables.
Use this to ensure all required configuration is present before starting the app.

Usage:
    from app.config import config, validate_required_env
    
    # Get configuration
    database_url = config.DATABASE_URL
    ollama_model = config.OLLAMA_MODEL
    
    # Validate required variables (raises error if missing)
    validate_required_env()
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Database
    DATABASE_URL: str
    
    # MongoDB
    MONGO_URI: Optional[str]
    MONGO_DB: str
    
    # Ollama LLM
    OLLAMA_MODEL: str
    OLLAMA_API_URL: Optional[str]
    
    # Application
    HOST: str
    PORT: int
    ENVIRONMENT: str
    DEBUG: bool
    
    # CORS
    CORS_ORIGINS: str
    
    # File Processing
    MAX_UPLOAD_SIZE_MB: int
    TESSERACT_CMD: Optional[str]
    
    # Embeddings & RAG
    EMBEDDING_MODEL: str
    RAG_TOP_K: int
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int
    
    # Logging
    LOG_LEVEL: str
    LOG_FILE: Optional[str]
    
    # Security (optional for now)
    SECRET_KEY: Optional[str]
    JWT_EXPIRATION_MINUTES: int
    RATE_LIMIT_PER_MINUTE: int


def load_config() -> Config:
    """Load configuration from environment variables with sensible defaults."""
    
    return Config(
        # Database
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///./backend_dev.db"),
        
        # MongoDB
        MONGO_URI=os.getenv("MONGO_URI") or None,
        MONGO_DB=os.getenv("MONGO_DB", "cv_repo"),
        
        # Ollama LLM
        OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct"),
        OLLAMA_API_URL=os.getenv("OLLAMA_API_URL") or None,
        
        # Application
        HOST=os.getenv("HOST", "0.0.0.0"),
        PORT=int(os.getenv("PORT", "8000")),
        ENVIRONMENT=os.getenv("ENVIRONMENT", "development"),
        DEBUG=os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"),
        
        # CORS
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "*"),
        
        # File Processing
        MAX_UPLOAD_SIZE_MB=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
        TESSERACT_CMD=os.getenv("TESSERACT_CMD") or None,
        
        # Embeddings & RAG
        EMBEDDING_MODEL=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        RAG_TOP_K=int(os.getenv("RAG_TOP_K", "5")),
        CHUNK_SIZE=int(os.getenv("CHUNK_SIZE", "500")),
        CHUNK_OVERLAP=int(os.getenv("CHUNK_OVERLAP", "100")),
        
        # Logging
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        LOG_FILE=os.getenv("LOG_FILE") or None,
        
        # Security
        SECRET_KEY=os.getenv("SECRET_KEY") or None,
        JWT_EXPIRATION_MINUTES=int(os.getenv("JWT_EXPIRATION_MINUTES", "60")),
        RATE_LIMIT_PER_MINUTE=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    )


def validate_required_env(environment: str = None) -> None:
    """
    Validate that all required environment variables are set.
    
    Args:
        environment: Target environment (development, production, etc.)
                    If None, uses ENVIRONMENT variable
    
    Raises:
        EnvironmentError: If required variables are missing
    """
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    # Variables required in all environments
    always_required = []
    
    # Additional variables required in production
    production_required = [
        "SECRET_KEY",
        "DATABASE_URL",
    ]
    
    required = always_required.copy()
    if env == "production":
        required.extend(production_required)
    
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables for '{env}' environment: {', '.join(missing)}\n"
            f"Please check your .env file or set these variables in your environment.\n"
            f"See ENV_SETUP_GUIDE.md for details."
        )


def print_config_summary(config: Config) -> None:
    """Print a summary of the current configuration (for debugging)."""
    print("\n" + "="*60)
    print("CONFIGURATION SUMMARY")
    print("="*60)
    print(f"Environment:        {config.ENVIRONMENT}")
    print(f"Debug Mode:         {config.DEBUG}")
    print(f"Host:Port:          {config.HOST}:{config.PORT}")
    print(f"\nDatabase:")
    print(f"  URL:              {_mask_password(config.DATABASE_URL)}")
    print(f"\nMongoDB:")
    print(f"  URI:              {_mask_password(config.MONGO_URI) if config.MONGO_URI else '(not configured - using local files)'}")
    print(f"  Database:         {config.MONGO_DB}")
    print(f"\nOllama LLM:")
    print(f"  Model:            {config.OLLAMA_MODEL}")
    print(f"  API URL:          {config.OLLAMA_API_URL or '(not set - using CLI)'}")
    print(f"\nFile Processing:")
    print(f"  Max Upload Size:  {config.MAX_UPLOAD_SIZE_MB} MB")
    print(f"  Tesseract:        {config.TESSERACT_CMD or '(auto-detect from PATH)'}")
    print(f"\nEmbeddings & RAG:")
    print(f"  Model:            {config.EMBEDDING_MODEL}")
    print(f"  Top-K Retrieval:  {config.RAG_TOP_K}")
    print(f"  Chunk Size:       {config.CHUNK_SIZE}")
    print(f"  Chunk Overlap:    {config.CHUNK_OVERLAP}")
    print(f"\nSecurity:")
    print(f"  Secret Key:       {'(set)' if config.SECRET_KEY else '(not set - required for production)'}")
    print(f"  CORS Origins:     {config.CORS_ORIGINS}")
    print("="*60 + "\n")


def _mask_password(url: Optional[str]) -> str:
    """Mask password in connection strings for safe logging."""
    if not url:
        return ""
    
    # Simple password masking for common formats
    import re
    
    # Pattern: scheme://user:password@host...
    pattern = r'(://[^:]+:)([^@]+)(@)'
    masked = re.sub(pattern, r'\1****\3', url)
    
    return masked


# Create a global config instance
config = load_config()


if __name__ == "__main__":
    """
    Run this script to test configuration loading and validation.
    
    Usage:
        python -m app.config
    """
    try:
        cfg = load_config()
        print_config_summary(cfg)
        
        # Try validation
        print("\nValidating configuration...")
        validate_required_env()
        print("✓ All required variables are set for current environment")
        
    except Exception as e:
        print(f"\n✗ Configuration error: {e}")
        exit(1)
