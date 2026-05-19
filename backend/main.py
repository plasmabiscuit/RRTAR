from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import contacts as contacts_service
from . import store
from .pipeline import JOB_SPECS
from .settings import Settings

settings = Settings.load()
settings.ensure_dirs()
store.init_db(settings)

app = FastAPI(title="RRTAR Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: Annotated[Optional[str], Header()] = None) -> None:
    expected = settings.shared_api_key.strip()
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


@app.get("/health")
@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "app_dir": str(settings.app_dir),
        "db_path": str(settings.db_path),
    }


@app.get("/config/reference", dependencies=[Depends(require_api_key)])
@app.get("/api/config/reference", dependencies=[Depends(require_api_key)])
def config_reference() -> Dict[str, Any]:
    contacts_path = _contacts_path()
    contacts_count = 0
    if contacts_path.exists():
        contacts_count = len(contacts_service.load_contacts(contacts_path))

    selector_profiles = []
    config_root = _reference_dir(settings.config_dir, settings.app_dir / "config")
    for path in sorted(config_root.glob("selector_profile*.json")):
        selector_profiles.append(path.name)

    form_version = {}
    form_version_path = _reference_path(settings.config_dir / "form_version.json", settings.app_dir / "config" / "form_version.json")
    if form_version_path.exists():
        form_version = json.loads(form_version_path.read_text())

    return {
        "form_version": form_version,
        "role_mapping": _read_json_if_exists(_reference_path(settings.config_dir / "role_mapping.json", settings.app_dir / "config" / "role_mapping.json")),
        "selector_profiles": selector_profiles,
        "contacts_count": contacts_count,
        "pipeline_support": _pipeline_support_summary(selector_profiles),
    }


@app.get("/contacts/search", dependencies=[Depends(require_api_key)])
@app.get("/api/contacts/search", dependencies=[Depends(require_api_key)])
def contacts_search(query: str = "", limit: int = 24) -> Dict[str, Any]:
    contacts = contacts_service.load_contacts(_contacts_path())
    return contacts_service.search_contacts(contacts, query, limit)


@app.post("/jobs/keyperson", dependencies=[Depends(require_api_key)])
@app.post("/api/jobs/keyperson", dependencies=[Depends(require_api_key)])
async def create_keyperson_job(
    files: List[UploadFile] = File(...),
    agency: str = Form("default"),
) -> Dict[str, Any]:
    return await _create_job("keyperson", files, agency)


@app.post("/jobs/budget", dependencies=[Depends(require_api_key)])
@app.post("/api/jobs/budget", dependencies=[Depends(require_api_key)])
async def create_budget_job(
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    return await _create_job("budget", files, "default")


@app.post("/jobs/performance-site", dependencies=[Depends(require_api_key)])
@app.post("/api/jobs/performance-site", dependencies=[Depends(require_api_key)])
async def create_performance_site_job(
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    return await _create_job("performance-site", files, "default")


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job(job_id: str) -> Dict[str, Any]:
    job = store.get_job(settings, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _serialize_job(job)


@app.get("/jobs/{job_id}/manifest", dependencies=[Depends(require_api_key)])
@app.get("/api/jobs/{job_id}/manifest", dependencies=[Depends(require_api_key)])
def get_manifest(job_id: str):
    job = _require_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed.")
    manifest_path = job.get("manifest_path")
    if not manifest_path:
        raise HTTPException(status_code=404, detail="Manifest not found.")
    return json.loads(Path(manifest_path).read_text())


@app.get("/jobs/{job_id}/validation", dependencies=[Depends(require_api_key)])
@app.get("/api/jobs/{job_id}/validation", dependencies=[Depends(require_api_key)])
def get_validation(job_id: str):
    job = _require_job(job_id)
    validation_path = job.get("validation_path")
    if not validation_path:
        raise HTTPException(status_code=404, detail="Validation output not found.")
    return json.loads(Path(validation_path).read_text())


@app.get("/jobs/{job_id}/artifacts", dependencies=[Depends(require_api_key)])
@app.get("/api/jobs/{job_id}/artifacts", dependencies=[Depends(require_api_key)])
def get_artifacts(job_id: str) -> Dict[str, Any]:
    job = _require_job(job_id)
    return {"job_id": job_id, "artifacts": job.get("artifacts", [])}


@app.get("/jobs/{job_id}/artifacts/file", dependencies=[Depends(require_api_key)])
@app.get("/api/jobs/{job_id}/artifacts/file", dependencies=[Depends(require_api_key)])
def get_artifact_file(job_id: str, path: str):
    job = _require_job(job_id)
    workspace_dir = job.get("workspace_dir")
    if not workspace_dir:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    resolved = (Path(workspace_dir) / path).resolve()
    workspace_root = Path(workspace_dir).resolve()
    if workspace_root not in resolved.parents and resolved != workspace_root:
        raise HTTPException(status_code=400, detail="Invalid artifact path.")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(resolved)


async def _create_job(job_type: str, files: List[UploadFile], agency: str) -> Dict[str, Any]:
    if job_type not in JOB_SPECS:
        raise HTTPException(status_code=400, detail="Unsupported job type.")
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    job_root = settings.tmp_dir / "jobs" / "incoming"
    job_root.mkdir(parents=True, exist_ok=True)
    upload_dir = job_root / store.utc_now().replace(":", "-")
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_filenames: List[str] = []
    for upload in files:
        safe_name = Path(upload.filename or "upload.pdf").name
        destination = upload_dir / safe_name
        with destination.open("wb") as fh:
            shutil.copyfileobj(upload.file, fh)
        original_filenames.append(safe_name)

    job = store.create_job(
        settings,
        job_type=job_type,
        agency=agency,
        upload_dir=upload_dir,
        original_filenames=original_filenames,
    )
    return _serialize_job(job)


def _require_job(job_id: str) -> Dict[str, Any]:
    job = store.get_job(settings, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": job["id"],
        "job_type": job["job_type"],
        "status": job["status"],
        "agency": job.get("agency"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "original_filenames": job.get("original_filenames", []),
        "error_text": job.get("error_text"),
        "result": job.get("result"),
    }


def _read_json_if_exists(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _reference_path(preferred: Path, fallback: Path) -> Path:
    return preferred if preferred.exists() else fallback


def _reference_dir(preferred: Path, fallback: Path) -> Path:
    if preferred.exists() and any(preferred.iterdir()):
        return preferred
    return fallback


def _contacts_path() -> Path:
    return _reference_path(settings.data_dir / "contacts.json", settings.app_dir / "data" / "contacts.json")


def _pipeline_support_summary(selector_profiles: List[str]) -> Dict[str, Dict[str, Any]]:
    schemas_root = _reference_dir(settings.schemas_dir, settings.app_dir / "schemas")
    config_root = _reference_dir(settings.config_dir, settings.app_dir / "config")
    selector_profile_set = set(selector_profiles)
    keyperson_schema = schemas_root / "RR_KeyPersonExpanded_4_0-V4.0.xsd"
    budget_reference = config_root / "RR_budget_reference.json"
    performance_reference = config_root / "selector_profile.grantsgov-performance-site-4.0.json"
    budget_selector = "selector_profile.grantsgov-rr-budget-3.0.json" in selector_profile_set
    performance_selector = performance_reference.name in selector_profile_set
    return {
        "keyperson": {
            "reference_type": "schema",
            "available": keyperson_schema.exists(),
            "name": keyperson_schema.name,
            "detail": "Grants.gov hosted schema is available on the backend." if keyperson_schema.exists() else "Grants.gov hosted schema is missing on the backend.",
            "validation_available": True,
        },
        "budget": {
            "reference_type": "reference",
            "available": budget_reference.exists() and budget_selector,
            "name": budget_reference.name,
            "detail": "Grants.gov hosted schema is available on the backend." if budget_reference.exists() and budget_selector else "Grants.gov hosted schema is missing on the backend.",
            "validation_available": False,
        },
        "performance-site": {
            "reference_type": "reference",
            "available": performance_reference.exists() and performance_selector,
            "name": performance_reference.name,
            "detail": "Grants.gov hosted schema is available on the backend." if performance_reference.exists() and performance_selector else "Grants.gov hosted schema is missing on the backend.",
            "validation_available": False,
        },
    }
