"""FastAPI server, REST endpoints, static UI host, and CLI entrypoint for KhemSAR."""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import threading
import time
import webbrowser
import zipfile
from pathlib import Path
from typing import Any

import httpx
import joblib
import pandas as pd
import uvicorn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from khemsar import __affiliation__, __author__, __license__, __version__
from khemsar.ai.copilot import parse_research_intent
from khemsar.ai.providers import list_ollama_models
from khemsar.ai.tutor import LESSONS, QUIZZES, answer_tutor_question
from khemsar.chemistry.curation import CurationConfig, curate_bioactivity_dataset
from khemsar.cloud.storage import (
    build_colab_notebook,
    build_dropbox_oauth_url,
    build_google_drive_direct_download_url,
    build_google_drive_oauth_url,
    detect_cloud_sync_folders,
    generate_pkce_pair,
    open_local_folder_in_file_manager,
    sync_bundle_to_folder,
)
from khemsar.connectors.orchestrator import run_multidb_search
from khemsar.connectors.rcsb_pdb import fetch_pdb_text, prepare_receptor_and_docking_box
from khemsar.core.config import AISettings, AppSettings, CloudSettings, load_settings, save_settings
from khemsar.core.i18n import load_locale
from khemsar.core.progress import get_progress, set_progress
from khemsar.core.project import ProjectManager
from khemsar.denovo.generator import generate_denovo_candidates
from khemsar.denovo.prep_3d import export_docking_md_library
from khemsar.plots.paper_figures import generate_all_paper_figures
from khemsar.qsar.modeling import LGBMRegressor, XGBRegressor, QSARTrainConfig, predict_with_qsar_bundle, train_and_validate_qsar
from khemsar.sar.activity_cliffs import compute_activity_cliffs_and_space
from khemsar.sar.interpretability import compute_shap_importance, generate_atomic_attribution_svg, render_molecule_svg
from khemsar.sar.mmp import analyze_matched_molecular_pairs
from khemsar.sar.rgroup import decompose_rgroups

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"
DEMO_CSV = PACKAGE_DIR / "data" / "demo_dataset.csv"

app = FastAPI(title="KhemSAR API", version=__version__, description="Paper-Ready QSAR/SAR & De Novo Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _pm() -> ProjectManager:
    env_ws = os.environ.get("KHEMSAR_WORKSPACE")
    if env_ws:
        return ProjectManager(env_ws)
    settings = load_settings()
    return ProjectManager(settings.workspace_root)


# ---------------- Pydantic Request Models ----------------
class SettingsPayload(BaseModel):
    language: str = "es"
    plot_language: str = "en"
    workspace_root: str | None = None
    ai: dict[str, Any] = Field(default_factory=dict)
    cloud: dict[str, Any] = Field(default_factory=dict)


class CreateProjectRequest(BaseModel):
    name: str = "KhemSAR_Study"
    target: str = ""
    description: str = ""


class ParseIntentRequest(BaseModel):
    description: str


class SearchRequest(BaseModel):
    target_query: str = ""
    chembl_target_id: str | None = None
    chembl_target_id: str | None = None
    pdb_id: str | None = None
    pubchem_aid: str | None = None
    standard_types: list[str] = Field(default_factory=lambda: ["IC50", "Ki", "Kd", "EC50"])
    min_confidence: int = 7
    max_records: int = 2000
    include_sources: list[str] | None = None


class PDBPrepareRequest(BaseModel):
    pdb_id: str | None = None
    pdb_text: str | None = None
    chain_id: str | None = None
    remove_waters: bool = True
    padding: float = 8.0


class CurateRequest(BaseModel):
    target_endpoint: str = "AUTO"
    task_type: str = "regression"
    activity_cutoff_pAct: float = 6.0
    max_duplicate_spread: float = 0.5
    canonicalize_tautomers: bool = True
    strip_salts: bool = True
    exclude_inorganics: bool = True
    exclude_organic_mixtures: bool = True


class TrainQSARRequest(BaseModel):
    task_type: str = "regression"
    feature_mode: str = "hybrid"
    n_bits: int = 512
    split_method: str = "scaffold"
    test_size: float = 0.2
    cv_folds: int = 5
    y_scrambling_permutations: int = 30
    algorithms: list[str] | None = None


class PredictRequest(BaseModel):
    smiles_list: list[str]


class SARRequest(BaseModel):
    similarity_cutoff: float = 0.65
    delta_p_cutoff: float = 1.0
    projection_method: str = "pca"
    core_smarts: str | None = None


class MoleculeSVGRequest(BaseModel):
    smiles: str
    width: int = 340
    height: int = 220


class DeNovoRequest(BaseModel):
    n_top_seeds: int = 8
    n_brics_samples: int = 30
    max_candidates: int = 35


class PlotRequest(BaseModel):
    dpi: int = 300
    plot_lang: str | None = None


class Export3DRequest(BaseModel):
    protonate_ph74: bool = True
    force_field: str = "MMFF94"
    max_molecules: int = 30


class TutorAskRequest(BaseModel):
    question: str
    lang: str = "es"
    project_id: str | None = None


class CloudSyncRequest(BaseModel):
    project_id: str
    target_folder: str | None = None


class CloudRevealRequest(BaseModel):
    project_id: str
    open_local: bool = True


class GDriveCSVImportRequest(BaseModel):
    drive_url: str


class OAuthURLRequest(BaseModel):
    provider: str  # gdrive | dropbox
    client_id: str
    redirect_uri: str | None = None


# ---------------- Core & Settings Endpoints ----------------
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "KhemSAR",
        "version": __version__,
        "author": __author__,
        "affiliation": __affiliation__,
        "license": __license__,
        "engines": {
            "rdkit": True,
            "xgboost": XGBRegressor is not None,
            "lightgbm": LGBMRegressor is not None,
        },
    }


@app.get("/api/locales/{lang}")
def get_locale(lang: str) -> dict[str, Any]:
    return load_locale(lang)


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    s = load_settings()
    return {
        "language": s.language,
        "plot_language": s.plot_language,
        "workspace_root": s.workspace_root,
        "ai": {
            "provider": s.ai.provider,
            "model": s.ai.model,
            "ollama_url": s.ai.ollama_url,
            "has_api_key": bool(s.ai.api_key),
        },
        "cloud": {
            "sync_provider": s.cloud.sync_provider,
            "custom_sync_dir": s.cloud.custom_sync_dir,
            "cloud_folder_url": s.cloud.cloud_folder_url,
            "gdrive_client_id": s.cloud.gdrive_client_id,
            "dropbox_app_key": s.cloud.dropbox_app_key,
        },
    }


@app.post("/api/settings")
def update_settings(payload: SettingsPayload) -> dict[str, Any]:
    current = load_settings()
    current.language = payload.language
    current.plot_language = payload.plot_language
    if payload.workspace_root:
        current.workspace_root = payload.workspace_root
    if payload.ai:
        current.ai = AISettings(
            provider=payload.ai.get("provider", current.ai.provider),
            model=payload.ai.get("model", current.ai.model),
            ollama_url=payload.ai.get("ollama_url", current.ai.ollama_url),
            api_key=payload.ai.get("api_key", current.ai.api_key) if payload.ai.get("api_key") not in (None, "***") else current.ai.api_key,
        )
    if payload.cloud:
        current.cloud = CloudSettings(
            sync_provider=payload.cloud.get("sync_provider", current.cloud.sync_provider),
            custom_sync_dir=payload.cloud.get("custom_sync_dir", current.cloud.custom_sync_dir),
            cloud_folder_url=payload.cloud.get("cloud_folder_url", current.cloud.cloud_folder_url),
            gdrive_client_id=payload.cloud.get("gdrive_client_id", current.cloud.gdrive_client_id),
            dropbox_app_key=payload.cloud.get("dropbox_app_key", current.cloud.dropbox_app_key),
        )
    saved_to = save_settings(current)
    return {"ok": True, "saved_to": str(saved_to)}


@app.get("/api/ai/ollama-models")
async def get_ollama_models() -> dict[str, Any]:
    s = load_settings()
    models = await list_ollama_models(s.ai.ollama_url)
    return {"models": models}


# ---------------- Projects & Demo ----------------
@app.get("/api/projects")
def list_projects() -> dict[str, Any]:
    return {"projects": _pm().list_projects()}


@app.post("/api/projects")
def create_project(req: CreateProjectRequest) -> dict[str, Any]:
    meta = _pm().create_project(req.name, description=req.description, target=req.target)
    return meta


@app.post("/api/projects/{project_id}/demo")
def load_demo_study(project_id: str) -> dict[str, Any]:
    pm = _pm()
    df = pd.read_csv(DEMO_CSV)
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    payload = {
        "query": "COX-2 / PTGS2 (Demo Study)",
        "resolved_target": {
            "chembl_target_id": "CHEMBL230",
            "uniprot_id": "P35354",
            "name": "Prostaglandin G/H synthase 2 (COX-2)",
        },
        "source_status": [
            {"source": "ChEMBL (Curated Demo)", "ok": True, "count": sum(1 for r in records if r["source"] == "ChEMBL")},
            {"source": "PubChem (Curated Demo)", "ok": True, "count": sum(1 for r in records if r["source"] == "PubChem")},
            {"source": "BindingDB (Curated Demo)", "ok": True, "count": sum(1 for r in records if r["source"] == "BindingDB")},
        ],
        "bioactivities": records,
        "pdb_structures": [
            {
                "pdb_id": "3LN1",
                "title": "Structure of Celecoxib Bound at the COX-2 Active Site",
                "resolution_angstrom": 2.4,
                "method": "X-RAY DIFFRACTION",
            },
            {
                "pdb_id": "1CX2",
                "title": "Cyclooxygenase-2 (Prostaglandin Synthase-2) Complexed with SC-558",
                "resolution_angstrom": 3.0,
                "method": "X-RAY DIFFRACTION",
            },
        ],
        "opentargets": [
            {
                "approved_symbol": "PTGS2",
                "approved_name": "Prostaglandin-endoperoxide synthase 2",
                "top_diseases": [{"disease": "Inflammation / Rheumatoid arthritis", "score": 0.89}],
            }
        ],
        "coconut_natural_products": [
            {"coconut_id": "CNP021456", "name": "Curcumin (natural COX-2 modulator)", "smiles": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O"}
        ],
    }
    pm.save_json(project_id, "raw/search_results.json", payload)
    pm.append_audit(project_id, "demo_loaded", {"raw_records": len(records)})
    return payload


def _normalize_csv_bytes_to_records(content: bytes, source_label: str) -> list[dict[str, Any]]:
    df = pd.read_csv(io.BytesIO(content))
    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl in ("smiles", "canonical_smiles", "smi"):
            col_map[c] = "smiles"
        elif cl in ("id", "compound_id", "mol_id", "chembl_id"):
            col_map[c] = "compound_id"
        elif cl in ("name", "compound_name"):
            col_map[c] = "name"
        elif cl in ("ic50", "ki", "kd", "ec50", "value", "standard_value", "activity"):
            col_map[c] = "standard_value"
        elif cl in ("pic50", "pki", "pactivity"):
            col_map[c] = "pActivity_direct"
        elif cl in ("units", "standard_units"):
            col_map[c] = "standard_units"
        elif cl in ("type", "standard_type", "endpoint"):
            col_map[c] = "standard_type"
    df = df.rename(columns=col_map)
    if "smiles" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain a 'smiles' column.")
    if "compound_id" not in df.columns:
        df["compound_id"] = [f"USER_{i+1:04d}" for i in range(len(df))]
    if "name" not in df.columns:
        df["name"] = df["compound_id"]
    if "pActivity_direct" in df.columns and "standard_value" not in df.columns:
        df["standard_value"] = 10.0 ** (-df["pActivity_direct"].astype(float)) * 1e9
        df["standard_units"] = "nM"
        df["standard_type"] = "IC50"
    if "standard_type" not in df.columns:
        df["standard_type"] = "IC50"
    if "standard_units" not in df.columns:
        df["standard_units"] = "nM"
    if "standard_relation" not in df.columns:
        df["standard_relation"] = "="
    df["source"] = source_label
    return df.where(pd.notnull(df), None).to_dict(orient="records")


@app.post("/api/projects/{project_id}/upload-csv")
async def upload_custom_csv(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    pm = _pm()
    content = await file.read()
    records = _normalize_csv_bytes_to_records(content, "User_CSV")
    payload = {
        "query": f"Uploaded CSV ({file.filename})",
        "source_status": [{"source": "User CSV", "ok": True, "count": len(records)}],
        "bioactivities": records,
        "pdb_structures": [],
    }
    pm.save_json(project_id, "raw/search_results.json", payload)
    pm.append_audit(project_id, "csv_uploaded", {"filename": file.filename, "rows": len(records)})
    return payload


@app.post("/api/projects/{project_id}/import-gdrive-csv")
async def import_gdrive_csv(project_id: str, req: GDriveCSVImportRequest) -> dict[str, Any]:
    dl_url = build_google_drive_direct_download_url(req.drive_url)
    if not dl_url:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google Drive file link. Share the CSV file and paste a link like https://drive.google.com/file/d/<ID>/view",
        )
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(dl_url)
            resp.raise_for_status()
            content = resp.content
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to download CSV from Google Drive: {exc}")

    records = _normalize_csv_bytes_to_records(content, "Google_Drive_CSV")
    pm = _pm()
    payload = {
        "query": "Imported Google Drive CSV",
        "source_status": [{"source": "Google Drive CSV", "ok": True, "count": len(records)}],
        "bioactivities": records,
        "pdb_structures": [],
    }
    pm.save_json(project_id, "raw/search_results.json", payload)
    pm.append_audit(project_id, "gdrive_csv_imported", {"rows": len(records)})
    return payload


# ---------------- Multi-DB Search & AI Copilot ----------------
@app.post("/api/ai/parse-intent")
async def api_parse_intent(req: ParseIntentRequest) -> dict[str, Any]:
    s = load_settings()
    return await parse_research_intent(req.description, s.ai)


@app.get("/api/projects/{project_id}/progress")
async def api_project_progress(project_id: str) -> dict[str, Any]:
    return get_progress(project_id)


@app.post("/api/projects/{project_id}/search")
async def api_multidb_search(project_id: str, req: SearchRequest) -> dict[str, Any]:
    if not (req.target_query or "").strip() and not (req.chembl_target_id or "").strip() and not (req.pdb_id or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Ingresa al menos una diana/proteína, ChEMBL ID o PDB ID para consultar las bases científicas.",
        )
    pm = _pm()
    cb = lambda pct, msg: set_progress(project_id, pct, msg, active=True)
    set_progress(project_id, 5, "Starting multi-database search...", active=True)
    try:
        res = await run_multidb_search(
            target_query=req.target_query,
            chembl_target_id=req.chembl_target_id,
            pdb_id=req.pdb_id,
            pubchem_aid=req.pubchem_aid,
            standard_types=tuple(req.standard_types),
            min_confidence=req.min_confidence,
            max_records=req.max_records,
            include_sources=req.include_sources,
            progress_cb=cb,
        )
        pm.save_json(project_id, "raw/search_results.json", res)
        pm.append_audit(
            project_id,
            "multidb_search",
            {"query": res.get("query", req.target_query), "pdb_id": req.pdb_id, "count": len(res.get("bioactivities", []))},
        )
        set_progress(project_id, 100, f"Search complete ({len(res.get('bioactivities', []))} records)", active=False)
        return res
    except Exception as exc:
        set_progress(project_id, 100, f"Search failed: {exc}", active=False)
        raise


# ---------------- 3D PDB Preparation ----------------
@app.post("/api/projects/{project_id}/pdb/prepare")
async def api_prepare_pdb(project_id: str, req: PDBPrepareRequest) -> dict[str, Any]:
    pm = _pm()
    pdb_raw = req.pdb_text or ""
    if not pdb_raw and req.pdb_id:
        try:
            pdb_raw = await fetch_pdb_text(req.pdb_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch PDB {req.pdb_id}: {exc}")
    if not pdb_raw:
        raise HTTPException(status_code=400, detail="Provide pdb_id or pdb_text.")

    prep = prepare_receptor_and_docking_box(
        pdb_raw,
        chain_id=req.chain_id or None,
        remove_waters=req.remove_waters,
        padding=req.padding,
    )
    pdir = pm.project_dir(project_id)
    (pdir / "docking_ready" / "receptor_raw.pdb").write_text(pdb_raw, encoding="utf-8")
    (pdir / "docking_ready" / "receptor_clean.pdb").write_text(prep["receptor_pdb"], encoding="utf-8")
    if prep["cocrystal_ligand_pdb"]:
        (pdir / "docking_ready" / "cocrystal_reference_ligand.pdb").write_text(
            prep["cocrystal_ligand_pdb"], encoding="utf-8"
        )
    pm.save_json(project_id, "docking_ready/pdb_meta.json", {"pdb_id": req.pdb_id, "docking_box": prep["docking_box"], "protein_atom_count": prep["protein_atom_count"]})
    pm.append_audit(project_id, "pdb_prepared", {"pdb_id": req.pdb_id, "protein_atoms": prep["protein_atom_count"]})
    return prep


# ---------------- Curation & QSAR Modeling ----------------
@app.post("/api/projects/{project_id}/curate")
def api_curate(project_id: str, req: CurateRequest) -> dict[str, Any]:
    pm = _pm()
    raw_data = pm.load_json(project_id, "raw/search_results.json")
    if not raw_data or not raw_data.get("bioactivities"):
        raise HTTPException(status_code=400, detail="No raw bioactivity records loaded in this project.")

    cfg = CurationConfig(
        target_endpoint=req.target_endpoint,
        task_type=req.task_type,
        activity_cutoff_pAct=req.activity_cutoff_pAct,
        max_duplicate_spread=req.max_duplicate_spread,
        canonicalize_tautomers=req.canonicalize_tautomers,
        strip_salts=req.strip_salts,
        exclude_inorganics=req.exclude_inorganics,
        exclude_organic_mixtures=req.exclude_organic_mixtures,
    )
    cb = lambda pct, msg: set_progress(project_id, pct, msg, active=True)
    set_progress(project_id, 5, "Starting chemical curation...", active=True)
    try:
        res = curate_bioactivity_dataset(raw_data["bioactivities"], cfg, progress_cb=cb)
        pm.save_json(project_id, "curated/curated.json", res)
        if res["curated_records"]:
            pd.DataFrame(res["curated_records"]).to_csv(pm.project_dir(project_id) / "curated" / "curated.csv", index=False)
        pm.append_audit(project_id, "curation", res["report"])
        set_progress(project_id, 100, f"Curation complete ({res['report']['final_count']} curated)", active=False)
        return res
    except Exception as exc:
        set_progress(project_id, 100, f"Curation failed: {exc}", active=False)
        raise


@app.post("/api/projects/{project_id}/qsar/train")
def api_train_qsar(project_id: str, req: TrainQSARRequest) -> dict[str, Any]:
    pm = _pm()
    curated = pm.load_json(project_id, "curated/curated.json")
    if not curated or not curated.get("curated_records"):
        raise HTTPException(status_code=400, detail="Run chemical curation first.")

    cfg = QSARTrainConfig(
        task_type=req.task_type,
        feature_mode=req.feature_mode,
        n_bits=req.n_bits,
        split_method=req.split_method,
        test_size=req.test_size,
        cv_folds=req.cv_folds,
        y_scrambling_permutations=req.y_scrambling_permutations,
        algorithms=req.algorithms,
    )
    bundle_path = str(pm.project_dir(project_id) / "models" / "qsar_bundle.joblib")
    cb = lambda pct, msg: set_progress(project_id, pct, msg, active=True)
    set_progress(project_id, 2, "Preparing QSAR training...", active=True)
    try:
        res = train_and_validate_qsar(curated["curated_records"], cfg, artifact_path=bundle_path, progress_cb=cb)
        pm.save_json(project_id, "models/qsar_result.json", res)
        pm.append_audit(project_id, "qsar_trained", {"best_algorithm": res["best_algorithm"], "metrics": res["best_metrics"]})
        set_progress(project_id, 100, f"QSAR complete ({res['best_algorithm']})", active=False)
        return res
    except ValueError as exc:
        set_progress(project_id, 100, str(exc), active=False)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        set_progress(project_id, 100, f"QSAR failed: {exc}", active=False)
        raise


@app.post("/api/projects/{project_id}/qsar/predict")
def api_predict_qsar(project_id: str, req: PredictRequest) -> dict[str, Any]:
    pm = _pm()
    bundle_path = pm.project_dir(project_id) / "models" / "qsar_bundle.joblib"
    if not bundle_path.exists():
        raise HTTPException(status_code=400, detail="Train a QSAR model first.")
    bundle = joblib.load(bundle_path)
    preds = predict_with_qsar_bundle(bundle, req.smiles_list)
    return {"predictions": preds}


# ---------------- SAR, Interpretability & 2D SVG ----------------
@app.post("/api/projects/{project_id}/sar/analyze")
def api_analyze_sar(project_id: str, req: SARRequest) -> dict[str, Any]:
    pm = _pm()
    curated = pm.load_json(project_id, "curated/curated.json")
    if not curated or not curated.get("curated_records"):
        raise HTTPException(status_code=400, detail="Run chemical curation first.")
    records = curated["curated_records"]

    try:
        set_progress(project_id, 15, "Computing Activity Cliffs (SALI) & Chemical Space...", active=True)
        cliffs = compute_activity_cliffs_and_space(
            records,
            similarity_cutoff=req.similarity_cutoff,
            delta_p_cutoff=req.delta_p_cutoff,
            projection_method=req.projection_method,
        )
        set_progress(project_id, 45, "Mining Matched Molecular Pairs (MMP)...", active=True)
        mmp = analyze_matched_molecular_pairs(records)
        set_progress(project_id, 70, "Running R-Group decomposition...", active=True)
        rgroup = decompose_rgroups(records, core_smarts=req.core_smarts)

        shap_res: dict[str, Any] = {"method": "not_trained", "top_features": []}
        bundle_path = pm.project_dir(project_id) / "models" / "qsar_bundle.joblib"
        if bundle_path.exists():
            set_progress(project_id, 85, "Computing SHAP descriptor importance...", active=True)
            bundle = joblib.load(bundle_path)
            shap_res = compute_shap_importance(bundle)

        sar_payload = {
            "activity_cliffs": cliffs,
            "mmp": mmp,
            "rgroup": rgroup,
            "shap": shap_res,
        }
        pm.save_json(project_id, "sar/sar_result.json", sar_payload)
        pm.append_audit(project_id, "sar_analyzed", {"n_cliffs": cliffs.get("n_cliffs_found", 0), "n_mmp": mmp.get("n_unique_transforms", 0)})
        set_progress(project_id, 100, "SAR analysis complete", active=False)
        return sar_payload
    except Exception as exc:
        set_progress(project_id, 100, f"SAR failed: {exc}", active=False)
        raise


@app.get("/api/molecule/svg")
def api_mol_svg_get(smiles: str, width: int = 240, height: int = 160) -> Response:
    svg = render_molecule_svg(smiles, width=width, height=height)
    if not svg:
        raise HTTPException(status_code=400, detail="Invalid SMILES.")
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/api/molecule/svg")
def api_mol_svg(req: MoleculeSVGRequest) -> Response:
    svg = render_molecule_svg(req.smiles, width=req.width, height=req.height)
    if not svg:
        raise HTTPException(status_code=400, detail="Invalid SMILES.")
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/molecule/3d-pdb")
def api_mol_3d_pdb(smiles: str, protonate_ph74: bool = True) -> dict[str, Any]:
    from rdkit import Chem
    from khemsar.denovo.prep_3d import generate_3d_conformer

    mol_3d, meta = generate_3d_conformer(smiles, protonate_ph74=protonate_ph74)
    if mol_3d is None:
        raise HTTPException(status_code=400, detail=meta.get("error", "3D generation failed."))
    return {"pdb_block": Chem.MolToPDBBlock(mol_3d), **meta}


@app.post("/api/projects/{project_id}/sar/atomic-map")
def api_atomic_map(project_id: str, req: MoleculeSVGRequest) -> dict[str, Any]:
    pm = _pm()
    bundle_path = pm.project_dir(project_id) / "models" / "qsar_bundle.joblib"
    if not bundle_path.exists():
        raise HTTPException(status_code=400, detail="Train a QSAR model first to compute atomic attribution.")
    bundle = joblib.load(bundle_path)
    return generate_atomic_attribution_svg(bundle, req.smiles, width=req.width, height=req.height)


# ---------------- De Novo Generation, Paper Plots & 3D Export ----------------
@app.post("/api/projects/{project_id}/denovo/generate")
def api_denovo_generate(project_id: str, req: DeNovoRequest) -> dict[str, Any]:
    pm = _pm()
    curated = pm.load_json(project_id, "curated/curated.json")
    bundle_path = pm.project_dir(project_id) / "models" / "qsar_bundle.joblib"
    if not curated or not bundle_path.exists():
        raise HTTPException(status_code=400, detail="Curate data and train QSAR model before de novo design.")
    bundle = joblib.load(bundle_path)
    sar_res = pm.load_json(project_id, "sar/sar_result.json") or {}
    mmp_transforms = sar_res.get("mmp", {}).get("transforms", [])

    cb = lambda pct, msg: set_progress(project_id, pct, msg, active=True)
    set_progress(project_id, 5, "Starting bioisosteric & de novo generation...", active=True)
    try:
        res = generate_denovo_candidates(
            curated_records=curated["curated_records"],
            qsar_bundle=bundle,
            mmp_transforms=mmp_transforms,
            n_top_seeds=req.n_top_seeds,
            n_brics_samples=req.n_brics_samples,
            max_candidates=req.max_candidates,
            progress_cb=cb,
        )
        pm.save_json(project_id, "denovo/candidates.json", res)
        pm.append_audit(project_id, "denovo_generated", {"n_generated": res["n_generated"]})
        set_progress(project_id, 100, f"Generated {res['n_generated']} candidates", active=False)
        return res
    except Exception as exc:
        set_progress(project_id, 100, f"De Novo failed: {exc}", active=False)
        raise


@app.post("/api/projects/{project_id}/plots/generate")
def api_generate_plots(project_id: str, req: PlotRequest) -> dict[str, Any]:
    pm = _pm()
    s = load_settings()
    plot_lang = req.plot_lang or ("en" if s.plot_language == "en" else s.language)
    qsar_res = pm.load_json(project_id, "models/qsar_result.json")
    sar_res = pm.load_json(project_id, "sar/sar_result.json")
    denovo_res = pm.load_json(project_id, "denovo/candidates.json")

    sar_space = sar_res.get("activity_cliffs") if sar_res else None
    shap_res = sar_res.get("shap") if sar_res else None

    saved = generate_all_paper_figures(
        output_dir=pm.project_dir(project_id) / "plots",
        qsar_result=qsar_res,
        sar_result=sar_space,
        shap_result=shap_res,
        denovo_result=denovo_res,
        plot_lang=plot_lang,
        dpi=req.dpi,
    )
    # Expose relative filenames for frontend
    rel_map = {
        k: {ext: Path(p).name for ext, p in fmt_map.items()}
        for k, fmt_map in saved.items()
    }
    pm.save_json(project_id, "plots/manifest.json", rel_map)
    return {"plot_lang": plot_lang, "dpi": req.dpi, "figures": rel_map}


@app.get("/api/projects/{project_id}/plots/file/{filename}")
def api_get_plot_file(project_id: str, filename: str) -> FileResponse:
    pm = _pm()
    safe_name = Path(filename).name
    target = (pm.project_dir(project_id) / "plots" / safe_name).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Plot file not found.")
    return FileResponse(target)


@app.post("/api/projects/{project_id}/export-3d")
def api_export_3d(project_id: str, req: Export3DRequest) -> dict[str, Any]:
    pm = _pm()
    denovo_res = pm.load_json(project_id, "denovo/candidates.json")
    if not denovo_res or not denovo_res.get("candidates"):
        raise HTTPException(status_code=400, detail="Generate de novo candidates first.")

    pdir = pm.project_dir(project_id)
    docking_dir = pdir / "docking_ready"
    rec_pdb_path = docking_dir / "receptor_clean.pdb"
    lig_pdb_path = docking_dir / "cocrystal_reference_ligand.pdb"
    pdb_meta = pm.load_json(project_id, "docking_ready/pdb_meta.json") or {}

    cands = denovo_res["candidates"][: req.max_molecules]
    cb = lambda pct, msg: set_progress(project_id, pct, msg, active=True)
    set_progress(project_id, 3, "Preparing 3D conformers...", active=True)
    try:
        out = export_docking_md_library(
            candidates=cands,
            output_dir=docking_dir,
            protonate_ph74=req.protonate_ph74,
            force_field=req.force_field,
            receptor_pdb=rec_pdb_path.read_text(encoding="utf-8") if rec_pdb_path.exists() else "",
            cocrystal_ligand_pdb=lig_pdb_path.read_text(encoding="utf-8") if lig_pdb_path.exists() else "",
            docking_box=pdb_meta.get("docking_box"),
            progress_cb=cb,
        )

        # Package docking_ready folder into one downloadable ZIP
        zip_path = docking_dir / "khemsar_docking_md_bundle.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in docking_dir.rglob("*"):
                if item.is_file() and item != zip_path:
                    zf.write(item, arcname=item.relative_to(docking_dir))

        pm.append_audit(project_id, "exported_3d_docking_md", {"n_3d_embedded": out["n_3d_embedded"]})
        set_progress(project_id, 100, f"3D export complete ({out['n_3d_embedded']} conformers)", active=False)
        return {
            "n_total": out["n_total"],
            "n_3d_embedded": out["n_3d_embedded"],
            "download_zip": "docking_ready/khemsar_docking_md_bundle.zip",
            "download_sdf": "docking_ready/khemsar_denovo_3d.sdf",
            "download_csv": "docking_ready/khemsar_denovo_library.csv",
            "download_xlsx": "docking_ready/khemsar_denovo_library.xlsx",
            "summary_rows": out["summary_rows"][:10],
        }
    except Exception as exc:
        set_progress(project_id, 100, f"3D export failed: {exc}", active=False)
        raise


@app.get("/api/projects/{project_id}/download/{subpath:path}")
def api_download_artifact(project_id: str, subpath: str) -> FileResponse:
    pm = _pm()
    pdir = pm.project_dir(project_id)
    target = (pdir / subpath).resolve()
    if pdir not in target.parents or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(target, filename=target.name)


# ---------------- AI Scientific Tutor ----------------
@app.get("/api/tutor/curriculum")
def api_tutor_curriculum(lang: str = "es") -> dict[str, Any]:
    code = lang if lang in ("es", "en", "pt") else "es"
    return {"lessons": LESSONS[code], "quizzes": QUIZZES[code]}


@app.post("/api/tutor/ask")
async def api_tutor_ask(req: TutorAskRequest) -> dict[str, Any]:
    s = load_settings()
    study_context: dict[str, Any] = {}
    if req.project_id:
        pm = _pm()
        study_context = {
            "curation": pm.load_json(req.project_id, "curated/curated.json"),
            "qsar": pm.load_json(req.project_id, "models/qsar_result.json"),
            "sar": pm.load_json(req.project_id, "sar/sar_result.json"),
            "denovo": pm.load_json(req.project_id, "denovo/candidates.json"),
        }
    return await answer_tutor_question(req.question, lang=req.lang, ai_settings=s.ai, study_context=study_context)


# ---------------- Cloud Storage (Gmail/Drive, Dropbox, TeraBox, Colab) ----------------
@app.get("/api/cloud/detect")
def api_cloud_detect() -> dict[str, Any]:
    return {"folders": detect_cloud_sync_folders()}


@app.post("/api/cloud/sync")
def api_cloud_sync(req: CloudSyncRequest) -> dict[str, Any]:
    pm = _pm()
    bundle = pm.export_bundle(req.project_id)
    s = load_settings()
    dest = req.target_folder or s.cloud.custom_sync_dir
    if not dest:
        detected = [f for f in detect_cloud_sync_folders() if f["detected_path"]]
        if detected:
            dest = detected[0]["detected_path"]
    if dest:
        sync_res = sync_bundle_to_folder(bundle, dest)
        return {"bundle_path": str(bundle), **sync_res}
    return {
        "ok": True,
        "bundle_path": str(bundle),
        "synced_path": "",
        "message": "Portable .qsarproj.zip created locally; select a TeraBox/Drive/Dropbox folder or download the bundle.",
    }


@app.post("/api/cloud/reveal-bundle")
def api_cloud_reveal_bundle(req: CloudRevealRequest) -> dict[str, Any]:
    pm = _pm()
    bundle = pm.export_bundle(req.project_id)
    opened = open_local_folder_in_file_manager(bundle) if req.open_local else False
    s = load_settings()
    return {
        "ok": True,
        "bundle_name": bundle.name,
        "bundle_path": str(bundle),
        "local_folder_opened": opened,
        "cloud_folder_url": s.cloud.cloud_folder_url,
        "download_url": f"/api/projects/{req.project_id}/bundle",
    }


@app.get("/api/projects/{project_id}/bundle")
def api_download_project_bundle(project_id: str) -> FileResponse:
    pm = _pm()
    bundle = pm.export_bundle(project_id)
    return FileResponse(bundle, filename=bundle.name)


@app.post("/api/cloud/oauth-url")
def api_oauth_url(req: OAuthURLRequest, request: Request) -> dict[str, Any]:
    verifier, challenge = generate_pkce_pair()
    redirect_uri = req.redirect_uri or f"{str(request.base_url).rstrip('/')}/api/cloud/oauth-callback"
    if req.provider == "gdrive":
        url = build_google_drive_oauth_url(req.client_id, redirect_uri, challenge)
    elif req.provider == "dropbox":
        url = build_dropbox_oauth_url(req.client_id, redirect_uri, challenge)
    else:
        raise HTTPException(status_code=400, detail="Supported OAuth providers: gdrive, dropbox.")
    return {"auth_url": url, "redirect_uri": redirect_uri, "code_verifier_hint": verifier[:12] + "..."}


@app.get("/api/projects/{project_id}/colab-notebook")
def api_colab_notebook(project_id: str) -> JSONResponse:
    pm = _pm()
    meta = pm.load_json(project_id, "project.json") or {"name": project_id, "target": "PTGS2"}
    nb = build_colab_notebook(meta.get("name", project_id), target_query=meta.get("target") or "PTGS2")
    return JSONResponse(
        content=nb,
        headers={"Content-Disposition": f'attachment; filename="KhemSAR_{project_id}.ipynb"'},
    )


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


def _is_khemsar_running(host: str, port: int) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=0.8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("app") == "KhemSAR"
    except Exception:
        return False


def _open_browser_when_ready(host: str, port: int) -> None:
    url = f"http://{host}:{port}"
    deadline = time.time() + 30.0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.25)


def _find_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
    for offset in range(max_tries):
        cand = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, cand))
                return cand
            except OSError:
                continue
    return preferred_port


def cli() -> None:
    parser = argparse.ArgumentParser(description="Launch KhemSAR scientific platform")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if _is_khemsar_running(args.host, args.port):
        print(f"[KhemSAR] Already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return

    port = _find_available_port(args.host, args.port)
    if port != args.port:
        print(f"[KhemSAR] Port {args.port} busy; starting on http://{args.host}:{port}")

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready, args=(args.host, port), daemon=True
        ).start()
    uvicorn.run(app, host=args.host, port=port)


if __name__ == "__main__":
    cli()
