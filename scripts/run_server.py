#!/usr/bin/env python3
"""
CLI Server Runner for the Multi-Cloud Infrastructure Provisioner.
"""
import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
from app.config import settings


def main():
    print(f"=================================================================")
    print(f"  Starting {settings.APP_NAME}")
    print(f"  Version: {settings.APP_VERSION}")
    print(f"  Environment: {settings.ENVIRONMENT}")
    print(f"  Database: {settings.DB_PATH}")
    print(f"  API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"=================================================================")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()
