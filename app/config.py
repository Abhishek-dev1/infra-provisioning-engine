"""
Application Configuration Module.
Provides centralized settings via Pydantic BaseSettings, supporting environment variable overrides.
"""
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    # Service Information
    APP_NAME: str = "Multi-Cloud & Virtualized Infrastructure Provisioning Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # Storage & Database
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DB_PATH: str = str(BASE_DIR / "provisioner.db")

    # Terraform Configuration
    TERRAFORM_BIN: str = "terraform"
    TERRAFORM_RUN_DIR: str = str(BASE_DIR / "runs")
    TERRAFORM_TEMPLATES_DIR: str = str(BASE_DIR / "terraform" / "templates")
    SIMULATE_TERRAFORM: bool = True  # Allows running in environments without cloud credentials / TF CLI

    # Orchestrator & Worker Configuration
    WORKER_POLL_INTERVAL_SECONDS: float = 0.5
    MAX_CONCURRENT_JOBS: int = 5
    ENABLE_BACKGROUND_WORKER: bool = True

    # Quotas & Limits (Default system threshold guardrails)
    DEFAULT_MAX_VCPU_PER_REQUEST: int = 64
    DEFAULT_MAX_RAM_GB_PER_REQUEST: int = 256
    DEFAULT_MAX_STORAGE_GB_PER_REQUEST: int = 2048
    DEFAULT_MAX_NODES_PER_REQUEST: int = 20

    # Verification Timers
    STORAGE_VERIFICATION_TIMEOUT_SECONDS: int = 30
    NODE_HEALTH_PROBE_INTERVAL_SECONDS: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
