"""Structure-Activity Landscape Index (SALI), Activity Cliffs, and 2D chemical space mapping."""

from __future__ import annotations

from typing import Any

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE


def compute_activity_cliffs_and_space(
    records: list[dict[str, Any]],
    similarity_cutoff: float = 0.65,
    delta_p_cutoff: float = 1.0,
    top_k: int = 25,
    projection_method: str = "pca",  # pca | tsne | umap
    random_state: int = 42,
) -> dict[str, Any]:
    """Compute pairwise SALI scores, top activity cliffs, and 2D chemical space coordinates."""
    if len(records) < 3:
        return {"cliffs": [], "space_points": [], "projection_used": projection_method}

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    mols = [Chem.MolFromSmiles(r["smiles"]) for r in records]
    valid_idx = [i for i, m in enumerate(mols) if m is not None]
    if len(valid_idx) < 3:
        return {"cliffs": [], "space_points": [], "projection_used": projection_method}

    fps = [gen.GetFingerprint(mols[i]) for i in valid_idx]
    fp_mat = np.zeros((len(valid_idx), 1024), dtype=float)
    for k, fp in enumerate(fps):
        DataStructs.ConvertToNumpyArray(fp, fp_mat[k])

    cliffs: list[dict[str, Any]] = []
    n = len(valid_idx)
    for a in range(n):
        sims = DataStructs.BulkTanimotoSimilarity(fps[a], fps[a + 1 :])
        ia = valid_idx[a]
        pa = float(records[ia]["pActivity"])
        for offset, sim in enumerate(sims):
            b = a + 1 + offset
            ib = valid_idx[b]
            pb = float(records[ib]["pActivity"])
            dp = abs(pa - pb)
            sali = dp / max(1e-3, 1.0 - sim)
            if sim >= similarity_cutoff and dp >= delta_p_cutoff:
                cliffs.append(
                    {
                        "mol1_id": records[ia]["compound_id"],
                        "mol1_name": records[ia]["name"],
                        "mol1_smiles": records[ia]["smiles"],
                        "mol1_pActivity": round(pa, 3),
                        "mol2_id": records[ib]["compound_id"],
                        "mol2_name": records[ib]["name"],
                        "mol2_smiles": records[ib]["smiles"],
                        "mol2_pActivity": round(pb, 3),
                        "tanimoto": round(float(sim), 4),
                        "delta_pActivity": round(float(dp), 3),
                        "SALI": round(float(sali), 2),
                    }
                )

    cliffs.sort(key=lambda x: x["SALI"], reverse=True)
    cliffs = cliffs[:top_k]

    # 2D chemical space projection
    used_proj = projection_method.lower()
    coords: np.ndarray
    if used_proj == "umap":
        try:
            import umap  # type: ignore

            reducer = umap.UMAP(n_components=2, metric="jaccard", random_state=random_state)
            coords = reducer.fit_transform(fp_mat)
        except Exception:
            used_proj = "tsne"

    if used_proj == "tsne":
        perp = max(2, min(30, (len(valid_idx) - 1) // 3))
        coords = TSNE(n_components=2, perplexity=perp, init="pca", learning_rate="auto", random_state=random_state).fit_transform(fp_mat)
    elif used_proj != "umap":
        used_proj = "pca"
        coords = PCA(n_components=2, random_state=random_state).fit_transform(fp_mat)

    space_points = [
        {
            "compound_id": records[idx]["compound_id"],
            "name": records[idx]["name"],
            "smiles": records[idx]["smiles"],
            "pActivity": float(records[idx]["pActivity"]),
            "active": int(records[idx].get("active", 0)),
            "x": round(float(coords[k, 0]), 4),
            "y": round(float(coords[k, 1]), 4),
        }
        for k, idx in enumerate(valid_idx)
    ]

    return {
        "projection_used": used_proj,
        "similarity_cutoff": similarity_cutoff,
        "delta_p_cutoff": delta_p_cutoff,
        "n_cliffs_found": len(cliffs),
        "cliffs": cliffs,
        "space_points": space_points,
    }
