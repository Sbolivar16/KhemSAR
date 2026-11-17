"""Fourches et al. chemical curation & bioactivity standardization protocol."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem.MolStandardize import rdMolStandardize

RDLogger.DisableLog("rdApp.*")

ORGANIC_ALLOWED_ATOMIC_NUMS = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 35, 53}

UNIT_TO_MOLAR = {
    "M": 1.0,
    "mol/L": 1.0,
    "mM": 1e-3,
    "uM": 1e-6,
    "µM": 1e-6,
    "nM": 1e-9,
    "pM": 1e-12,
    "fM": 1e-15,
}


@dataclass
class CurationConfig:
    target_endpoint: str = "IC50"  # IC50 | Ki | Kd | EC50 | AUTO
    task_type: str = "regression"  # regression | classification
    activity_cutoff_pAct: float = 6.0  # 1 uM cutoff for binary classification
    max_duplicate_spread: float = 0.5  # max log-unit spread before rejecting discordant replicates
    canonicalize_tautomers: bool = True
    strip_salts: bool = True
    exclude_inorganics: bool = True
    exclude_organic_mixtures: bool = True
    min_heavy_atoms: int = 6
    max_mw: float = 1000.0


def _to_p_activity(value: float, units: str, endpoint: str) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    u = (units or "nM").strip()
    if endpoint.lower().startswith("p") or u == "" and 1.0 <= value <= 14.0 and endpoint.startswith("p"):
        return float(value)
    if value <= 0:
        return None
    factor = UNIT_TO_MOLAR.get(u)
    if factor is None:
        u_lower = u.lower()
        for k, f in UNIT_TO_MOLAR.items():
            if k.lower() == u_lower:
                factor = f
                break
    if factor is None:
        return None
    molar = value * factor
    if molar <= 0:
        return None
    return float(-math.log10(molar))


def standardize_molecule(
    smiles: str,
    strip_salts: bool = True,
    exclude_inorganics: bool = True,
    exclude_organic_mixtures: bool = True,
    canonicalize_tautomers: bool = True,
    min_heavy_atoms: int = 6,
) -> tuple[Chem.Mol | None, str, str, str]:
    """Return (standardized_mol, canonical_smiles, inchikey, rejection_reason)."""
    if not smiles or not isinstance(smiles, str):
        return None, "", "", "empty_smiles"
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return None, "", "", "invalid_smiles"

    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if len(frags) > 1:
        heavy_frags = [f for f in frags if f.GetNumHeavyAtoms() >= min_heavy_atoms]
        if exclude_organic_mixtures and len(heavy_frags) > 1:
            return None, "", "", "organic_mixture"
        if strip_salts:
            chooser = rdMolStandardize.LargestFragmentChooser(preferOrganic=True)
            mol = chooser.choose(mol)
        else:
            return None, "", "", "salt_or_fragment"

    if exclude_inorganics:
        atomic_nums = {atom.GetAtomicNum() for atom in mol.GetAtoms()}
        if 6 not in atomic_nums:
            return None, "", "", "inorganic_no_carbon"
        if not atomic_nums.issubset(ORGANIC_ALLOWED_ATOMIC_NUMS):
            return None, "", "", "inorganic_or_organometallic"

    if mol.GetNumHeavyAtoms() < min_heavy_atoms:
        return None, "", "", "too_small"

    try:
        uncharger = rdMolStandardize.Uncharger()
        mol = uncharger.uncharge(mol)
        if canonicalize_tautomers:
            enumerator = rdMolStandardize.TautomerEnumerator()
            mol = enumerator.Canonicalize(mol)
        Chem.SanitizeMol(mol)
    except Exception:
        return None, "", "", "standardization_failed"

    can_smi = Chem.MolToSmiles(mol, isomericSmiles=False, canonical=True)
    inchikey = Chem.MolToInchiKey(mol)
    return mol, can_smi, inchikey, ""


def curate_bioactivity_dataset(
    records: list[dict[str, Any]] | pd.DataFrame,
    config: CurationConfig | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Execute Fourches et al. curation with PRISMA-like quantitative attrition log."""
    cfg = config or CurationConfig()
    df = pd.DataFrame(records) if not isinstance(records, pd.DataFrame) else records.copy()
    if df.empty:
        return {"curated_records": [], "report": {"raw_count": 0, "final_count": 0}, "endpoint_used": cfg.target_endpoint}

    raw_count = len(df)
    attrition: dict[str, int] = {
        "raw_count": raw_count,
        "excluded_endpoint_mismatch": 0,
        "excluded_censored_or_invalid_value": 0,
        "excluded_invalid_or_inorganic_or_mixture": 0,
        "excluded_mw_out_of_range": 0,
        "merged_duplicates": 0,
        "excluded_discordant_duplicates": 0,
        "final_count": 0,
    }
    rejection_breakdown: dict[str, int] = {}

    # Determine endpoint if AUTO
    endpoint = cfg.target_endpoint
    if endpoint == "AUTO" and "standard_type" in df.columns:
        counts = df["standard_type"].dropna().astype(str).value_counts()
        endpoint = str(counts.index[0]) if len(counts) > 0 else "IC50"

    valid_rows: list[dict[str, Any]] = []
    step_every = max(1, raw_count // 12)
    for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
        if progress_cb and (row_idx == 1 or row_idx % step_every == 0 or row_idx == raw_count):
            progress_cb(10 + int(75 * (row_idx / raw_count)), f"Standardizing molecules ({row_idx}/{raw_count})...")
        st_type = str(row.get("standard_type", endpoint) or endpoint).strip()
        if st_type.upper() != endpoint.upper():
            attrition["excluded_endpoint_mismatch"] += 1
            continue

        rel = str(row.get("standard_relation", "=") or "=").strip()
        val_raw = row.get("standard_value")
        units = str(row.get("standard_units", "nM") or "nM").strip()
        try:
            fval = float(val_raw)
        except (TypeError, ValueError):
            attrition["excluded_censored_or_invalid_value"] += 1
            continue

        p_act = _to_p_activity(fval, units, st_type)
        if p_act is None:
            attrition["excluded_censored_or_invalid_value"] += 1
            continue

        # Handle censored relations rigorously
        if cfg.task_type == "regression":
            if rel not in ("=", "~", "≈", ""):
                attrition["excluded_censored_or_invalid_value"] += 1
                continue
            binary_label = 1 if p_act >= cfg.activity_cutoff_pAct else 0
        else:
            if rel in ("=", "~", "≈", ""):
                binary_label = 1 if p_act >= cfg.activity_cutoff_pAct else 0
            elif rel in ("<", "<=") and p_act >= cfg.activity_cutoff_pAct:
                binary_label = 1
            elif rel in (">", ">=") and p_act < cfg.activity_cutoff_pAct:
                binary_label = 0
            else:
                attrition["excluded_censored_or_invalid_value"] += 1
                continue

        mol, can_smi, ikey, reason = standardize_molecule(
            smiles=str(row.get("smiles", "")),
            strip_salts=cfg.strip_salts,
            exclude_inorganics=cfg.exclude_inorganics,
            exclude_organic_mixtures=cfg.exclude_organic_mixtures,
            canonicalize_tautomers=cfg.canonicalize_tautomers,
            min_heavy_atoms=cfg.min_heavy_atoms,
        )
        if mol is None:
            attrition["excluded_invalid_or_inorganic_or_mixture"] += 1
            rejection_breakdown[reason] = rejection_breakdown.get(reason, 0) + 1
            continue

        from rdkit.Chem import Descriptors

        mw = Descriptors.MolWt(mol)
        if mw > cfg.max_mw:
            attrition["excluded_mw_out_of_range"] += 1
            continue

        valid_rows.append(
            {
                "compound_id": str(row.get("compound_id", "")),
                "name": str(row.get("name", "") or row.get("compound_id", "")),
                "original_smiles": str(row.get("smiles", "")),
                "smiles": can_smi,
                "inchikey": ikey,
                "standard_type": endpoint,
                "pActivity": round(p_act, 4),
                "active": int(binary_label),
                "year": row.get("year"),
                "source": str(row.get("source", "")),
                "assay_id": str(row.get("assay_id", "")),
            }
        )

    if not valid_rows:
        return {
            "curated_records": [],
            "report": attrition,
            "rejection_breakdown": rejection_breakdown,
            "endpoint_used": endpoint,
        }

    if progress_cb:
        progress_cb(90, "Aggregating InChIKey replicates...")
    vdf = pd.DataFrame(valid_rows)
    curated_list: list[dict[str, Any]] = []
    for ikey, grp in vdf.groupby("inchikey", sort=False):
        if len(grp) == 1:
            rec = grp.iloc[0].to_dict()
            rec["n_replicates"] = 1
            rec["pActivity_spread"] = 0.0
            curated_list.append(rec)
        else:
            vals = grp["pActivity"].to_numpy(dtype=float)
            spread = float(np.max(vals) - np.min(vals))
            if spread > cfg.max_duplicate_spread:
                attrition["excluded_discordant_duplicates"] += len(grp)
                continue
            attrition["merged_duplicates"] += len(grp) - 1
            med_p = float(np.median(vals))
            first = grp.iloc[0].to_dict()
            first["pActivity"] = round(med_p, 4)
            first["active"] = int(1 if med_p >= cfg.activity_cutoff_pAct else 0)
            first["n_replicates"] = len(grp)
            first["pActivity_spread"] = round(spread, 4)
            first["source"] = ",".join(sorted({str(s) for s in grp["source"] if s}))
            years = [int(y) for y in grp["year"].dropna().tolist() if str(y).isdigit()]
            first["year"] = min(years) if years else None
            curated_list.append(first)

    attrition["final_count"] = len(curated_list)
    return {
        "curated_records": curated_list,
        "report": attrition,
        "rejection_breakdown": rejection_breakdown,
        "endpoint_used": endpoint,
        "config": asdict(cfg),
    }
