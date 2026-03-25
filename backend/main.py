from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is on sys.path for absolute imports
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT.parent / ".env")

from database import SessionLocal, init_database
from routers import diagnosis, export, settings_router
from routers.admin_auth_router import router as admin_auth_router
from routers.admin_doctor_router import router as admin_doctor_router
from routers.admin_model_router import router as admin_model_router
from routers.admin_asr_router import router as admin_asr_router
from routers.doctor_auth_router import router as doctor_auth_router
from routers.consultation_router import router as consultation_router
from services.admin_bootstrap_service import AdminBootstrapService
from services.app_state_service import AppStateService
from services.auth_service import AuthService
from services.storage_service import StorageService
from services.asr_service import AsrService
from services.diarization_service import DiarizationService
from services.model_config_service import ModelConfigService
from ws.audio_ws import router as ws_router

app = FastAPI(title="Medical EMR Web Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = StorageService(root_dir=_BACKEND_ROOT)
storage.ensure_runtime_layout()
auth_service = AuthService(
    secret_key=os.getenv("ADMIN_AUTH_SECRET", "hospital-web-dev-secret")
)
app_state_service = AppStateService(prompt_dir=_BACKEND_ROOT / "prompts")

init_database()
with SessionLocal() as db:
    AdminBootstrapService(
        db=db, auth_service=auth_service, yaml_settings=storage.settings
    ).bootstrap()
    model_service = ModelConfigService(db)
    active_model = model_service.get_active_model_config()
    app_state_service.refresh_llm_services(app, active_model)

asr_service = AsrService(sample_dir=storage.sample_dir)
diarization_service = DiarizationService()

app.state.storage = storage
app.state.auth_service = auth_service
app.state.app_state_service = app_state_service
app.state.asr_service = asr_service
app.state.diarization_service = diarization_service
app.state.sessions = {}

app.include_router(diagnosis.router, prefix="/api/diagnosis", tags=["diagnosis"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(admin_auth_router, tags=["admin-auth"])
app.include_router(admin_model_router, tags=["admin-models"])
app.include_router(admin_asr_router, tags=["admin-asr"])
app.include_router(admin_doctor_router, tags=["admin-doctors"])
app.include_router(doctor_auth_router, tags=["doctor-auth"])
app.include_router(consultation_router, tags=["consultations"])
app.include_router(ws_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
