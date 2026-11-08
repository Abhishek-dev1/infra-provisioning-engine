"""
FastAPI Application Entrypoint.
Initializes the RESTful control-plane service, mounts routers, and configures middlewares.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.database import db
from app.api.routes_jobs import router as jobs_router
from app.api.routes_preflight import router as preflight_router
from app.api.routes_storage import router as storage_router
from app.api.routes_providers import router as providers_router
from app.api.routes_nodes import router as nodes_router
from app.api.routes_system import router as system_router


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Asynchronous Multi-Cloud & Virtualized Infrastructure Provisioning Engine. "
            "Automates pre-flight quota checks, Terraform IaC orchestration, "
            "storage volume attachment verification, and hybrid Kubernetes node bootstrapping "
            "across AWS, Azure, GCP, VMware (vSphere/ESXi), and KVM hypervisors."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Middleware Configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API Sub-routers
    api_prefix = settings.API_V1_PREFIX
    application.include_router(jobs_router, prefix=api_prefix)
    application.include_router(preflight_router, prefix=api_prefix)
    application.include_router(storage_router, prefix=api_prefix)
    application.include_router(providers_router, prefix=api_prefix)
    application.include_router(nodes_router, prefix=api_prefix)
    application.include_router(system_router)

    @application.get("/", tags=["Root"])
    def root():
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "ONLINE",
            "documentation": "/docs",
            "supported_clouds": ["AWS", "Azure", "GCP"],
            "supported_hypervisors": ["VMware vSphere/ESXi", "KVM/libvirt"],
            "capabilities": [
                "Automated Pre-Flight Quota & Capacity Checks",
                "Asynchronous Provisioning Control-Plane & Job Queue",
                "Terraform IaC Workspace & Execution Automation",
                "Storage Volume Attachment & I/O Verification",
                "Hybrid Kubernetes Worker Node Cloud-Init Bootstrapping",
                "Operational Audit Logging & Telemetry Health Probes"
            ]
        }

    @application.on_event("startup")
    def on_startup():
        db.init_schema()

    return application


app = create_app()
