"""
Configuration management using Pydantic Settings
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    API_VERSION: str = "v1"
    API_TITLE: str = "VLA Robot Assistant API"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Security
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database URLs
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "robot"
    POSTGRES_PASSWORD: str = "robot_pass"
    POSTGRES_DB: str = "robot_db"

    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "robotpassword"

    MONGODB_URI: str = "mongodb://mongodb:27017"
    MONGODB_DB: str = "robot_telemetry"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    HUGGINGFACE_TOKEN: Optional[str] = None
    WANDB_API_KEY: Optional[str] = None

    # LLM Configuration
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000

    # ROS2 Configuration
    ROS_DOMAIN_ID: int = 42
    RMW_IMPLEMENTATION: str = "rmw_cyclonedds_cpp"

    # MLflow
    MLFLOW_TRACKING_URI: str = "http://mlflow:5000"

    # Model paths
    MODEL_CACHE_DIR: str = "/root/.cache/huggingface"

    @property
    def database_url(self) -> str:
        """PostgreSQL connection URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def mongodb_url(self) -> str:
        """MongoDB connection URL"""
        return f"{self.MONGODB_URI}/{self.MONGODB_DB}"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
