"""Multi-objective de novo molecule generator combining bioisosterism and BRICS recombination."""

from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np
from rdkit import Chem
from rdkit.Chem import BRICS

from khemsar.denovo.bioisosteres import apply_bioisosteric_replacements
from khemsar.qsar.modeling import predict_with_qsar_bundle


def _compute_mpo_score(pred: dict[str, Any], y_min: float, y_max: float, task_type: str) -> float:
    """Compute Multi-Parameter Optimization score in [0, 1] balancing potency, AD, QED, SA & alerts."""
    if task_type == "classification":
        potency_norm = float(pred.get("predicted_prob") or pred.get("predicted_value") or 0.5)
    else:
        span = max(0.5, y_max - y_min)
        potency_norm = float(np.clip((pred["predicted_value"] - y_min) / span, 0.0, 1.25))
        potency_norm = min(1.0, potency_norm / 1.15)

    mc = pred["medchem"]
    qed = float(mc["QED"])
    sa_norm = float(np.clip((10.0 - mc["SA_Score"]) / 9.0, 0.0, 1.0))
    ad_bonus = 1.0 if pred["in_ad"] else (0.55 if (pred["in_leverage_ad"] or pred["in_similarity_ad"]) else 0.2)
    alert_penalty = 0.0
    if mc["PAINS_Alerts"]:
        alert_penalty += 0.25
    if mc["Brenk_Alerts"]:
        alert_penalty += 0.10
    if mc["Lipinski_Violations"] > 1:
        alert_penalty += 0.12

    score = (0.42 * potency_norm + 0.23 * ad_bonus + 0.20 * qed + 0.15 * sa_norm) - alert_penalty
    return round(float(np.clip(score, 0.0, 1.0)), 4)


def generate_denovo_candidates(
    curated_records: list[dict[str, Any]],
    qsar_bundle: dict[str, Any],
    mmp_transforms: list[dict[str, Any]] | None = None,
    n_top_seeds: int = 8,
    n_brics_samples: int = 35,
    max_candidates: int = 40,
    seed: int = 42,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Generate novel bioisosteric and BRICS-recombined molecules, scored by QSAR + AD + MedChem MPO."""
    rng = random.Random(seed)
    known_smiles = {r["smiles"] for r in curated_records}

    sorted_recs = sorted(curated_records, key=lambda r: float(r["pActivity"]), reverse=True)
    top_seeds = sorted_recs[: min(n_top_seeds, len(sorted_recs))]

    candidates_meta: dict[str, dict[str, str]] = {}

    if progress_cb:
        progress_cb(15, f"Applying bioisosteric replacements on top {len(top_seeds)} hits...")
    # 1. Bioisosteric replacements on top active hits
    for parent in top_seeds:
        variants = apply_bioisosteric_replacements(
            parent["smiles"], max_variants=18, mmp_transforms=mmp_transforms
        )
        for v in variants:
            smi = v["smiles"]
            if smi in known_smiles or smi in candidates_meta:
                continue
            candidates_meta[smi] = {
                "parent_id": parent["compound_id"],
                "parent_name": parent["name"],
                "origin": "Bioisostere",
                "rule_id": v["rule_id"],
                "rationale": v["description"],
            }

    if progress_cb:
        progress_cb(48, "Running BRICS fragment recombination...")
    # 2. BRICS fragment recombination across top seeds (scaffold hopping / sidechain crossover)
    seed_mols = [Chem.MolFromSmiles(r["smiles"]) for r in top_seeds if Chem.MolFromSmiles(r["smiles"]) is not None]
    frags: set[str] = set()
    for m in seed_mols:
        try:
            frags.update(BRICS.BRICSDecompose(m))
        except Exception:
            continue

    frag_mols = [Chem.MolFromSmiles(f) for f in sorted(frags) if Chem.MolFromSmiles(f) is not None]
    if len(frag_mols) >= 2:
        try:
            builder = BRICS.BRICSBuild(frag_mols)
            count = 0
            for prod in builder:
                if count >= n_brics_samples * 3:
                    break
                count += 1
                try:
                    Chem.SanitizeMol(prod)
                    if prod.GetNumHeavyAtoms() < 12 or prod.GetNumHeavyAtoms() > 48:
                        continue
                    can = Chem.MolToSmiles(prod, isomericSmiles=False, canonical=True)
                except Exception:
                    continue
                if can in known_smiles or can in candidates_meta:
                    continue
                candidates_meta[can] = {
                    "parent_id": "BRICS_Pool",
                    "parent_name": "Top-Hits BRICS Crossover",
                    "origin": "DeNovo_BRICS",
                    "rule_id": "BRICS_Recombination",
                    "rationale": "Medicinal chemistry fragment recombination across top active scaffolds",
                }
                if len(candidates_meta) >= max_candidates * 3:
                    break
        except Exception:
            pass

    if not candidates_meta:
        return {"n_generated": 0, "candidates": []}

    candidate_smiles = list(candidates_meta.keys())
    # Cap evaluation batch cleanly for speed
    if len(candidate_smiles) > max_candidates * 3:
        rng.shuffle(candidate_smiles)
        candidate_smiles = candidate_smiles[: max_candidates * 3]

    if progress_cb:
        progress_cb(76, f"Scoring {len(candidate_smiles)} candidates (QSAR + AD + QED + SA)...")
    preds = predict_with_qsar_bundle(qsar_bundle, candidate_smiles)
    y_train = np.asarray(qsar_bundle["y_train"], dtype=float)
    y_min, y_max = float(np.min(y_train)), float(np.max(y_train))
    task_type = qsar_bundle["task_type"]

    scored: list[dict[str, Any]] = []
    for idx, pred in enumerate(preds, start=1):
        smi = pred["smiles"]
        meta = candidates_meta[smi]
        mpo = _compute_mpo_score(pred, y_min, y_max, task_type)
        scored.append(
            {
                "candidate_id": f"KHEM_DN_{idx:03d}",
                "smiles": smi,
                "origin": meta["origin"],
                "bioisostere_rule": meta["rule_id"],
                "rationale": meta["rationale"],
                "parent_id": meta["parent_id"],
                "parent_name": meta["parent_name"],
                "predicted_pActivity": pred["predicted_value"] if task_type == "regression" else None,
                "predicted_active_prob": pred["predicted_prob"] if task_type == "classification" else None,
                "in_ad": pred["in_ad"],
                "leverage": pred["leverage"],
                "knn_tanimoto": pred["knn_tanimoto"],
                "MPO_score": mpo,
                **pred["medchem"],
            }
        )

    scored.sort(key=lambda x: (x["MPO_score"], x.get("predicted_pActivity") or 0.0), reverse=True)
    final_candidates = scored[:max_candidates]
    for rank, item in enumerate(final_candidates, start=1):
        item["rank"] = rank

    return {
        "n_generated": len(final_candidates),
        "n_evaluated": len(scored),
        "candidates": final_candidates,
    }
