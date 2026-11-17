"""OECD Principle 5 interpretability: SHAP global/local importance and 2D atomic attribution SVG maps."""

from __future__ import annotations

from typing import Any

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import SimilarityMaps, rdMolDraw2D

from khemsar.chemistry.descriptors import featurize_smiles_list


def render_molecule_svg(smiles: str, width: int = 340, height: int = 230) -> str:
    """Render a crisp 2D chemical structure SVG using RDKit."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    rdDepictor.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def compute_shap_importance(bundle: dict[str, Any], top_k: int = 15) -> dict[str, Any]:
    """Compute SHAP global feature importance across the trained QSAR pipeline."""
    pipe = bundle["pipeline"]
    X_train = bundle["X_train"]
    X_test = bundle["X_test"]
    feature_names = np.asarray(bundle["feature_names"])

    # Transform through VarianceThreshold + StandardScaler without leaking labels
    var_step = pipe.named_steps["var"]
    scaler_step = pipe.named_steps["scaler"]
    model = pipe.named_steps["model"]

    mask = var_step.get_support()
    active_names = feature_names[mask].tolist()
    X_tr_t = scaler_step.transform(var_step.transform(X_train))
    X_te_t = scaler_step.transform(var_step.transform(X_test))

    shap_values: np.ndarray | None = None
    method_used = "permutation_fallback"

    try:
        import shap

        bg = X_tr_t[: min(40, len(X_tr_t))]
        eval_x = X_te_t[: min(30, len(X_te_t))]
        model_cls = type(model).__name__
        if any(k in model_cls for k in ("Forest", "ExtraTrees", "XGB", "LGBM", "GradientBoosting")):
            try:
                explainer = shap.TreeExplainer(model)
                sv = explainer.shap_values(eval_x)
                method_used = "TreeExplainer"
            except Exception:
                explainer = shap.Explainer(model.predict, bg)
                sv = explainer(eval_x).values
                method_used = "PermutationExplainer"
        elif any(k in model_cls for k in ("Ridge", "ElasticNet", "Logistic", "PLS")):
            try:
                explainer = shap.LinearExplainer(model, bg)
                sv = explainer.shap_values(eval_x)
                method_used = "LinearExplainer"
            except Exception:
                explainer = shap.Explainer(model.predict, bg)
                sv = explainer(eval_x).values
                method_used = "Explainer"
        else:
            explainer = shap.Explainer(model.predict, bg)
            sv = explainer(eval_x).values
            method_used = "Explainer"

        if isinstance(sv, list):
            sv = sv[1] if len(sv) > 1 else sv[0]
        sv_arr = np.asarray(sv, dtype=float)
        if sv_arr.ndim == 3:
            sv_arr = sv_arr[:, :, 1] if sv_arr.shape[2] > 1 else sv_arr[:, :, 0]
        shap_values = sv_arr
    except Exception:
        shap_values = None

    if shap_values is not None and shap_values.shape[1] == len(active_names):
        mean_abs = np.mean(np.abs(shap_values), axis=0)
        # Signed correlation between feature value and SHAP value to indicate positive/negative direction
        signed_dir: list[float] = []
        eval_x_sub = X_te_t[: shap_values.shape[0]]
        for j in range(len(active_names)):
            col = eval_x_sub[:, j]
            sv_col = shap_values[:, j]
            if np.std(col) > 1e-9 and np.std(sv_col) > 1e-9:
                signed_dir.append(float(np.corrcoef(col, sv_col)[0, 1]))
            else:
                signed_dir.append(0.0)
    else:
        # Clean permutation importance fallback
        from sklearn.inspection import permutation_importance

        pi = permutation_importance(pipe, X_test, bundle["y_test"], n_repeats=5, random_state=42)
        mean_abs = np.maximum(0.0, pi.importances_mean[mask])
        signed_dir = [0.0] * len(active_names)
        method_used = "PermutationImportance"

    order = np.argsort(mean_abs)[::-1][:top_k]
    top_features = [
        {
            "feature": active_names[int(idx)],
            "mean_abs_shap": round(float(mean_abs[int(idx)]), 5),
            "direction_corr": round(float(signed_dir[int(idx)]), 3),
        }
        for idx in order
        if mean_abs[int(idx)] > 0
    ]
    return {"method": method_used, "top_features": top_features}


def generate_atomic_attribution_svg(
    bundle: dict[str, Any],
    smiles: str,
    width: int = 380,
    height: int = 260,
) -> dict[str, Any]:
    """Compute per-atom QSAR attribution weights via Morgan bit masking & render SVG map."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"svg": "", "atom_weights": []}

    pipe = bundle["pipeline"]
    feature_mode = bundle["feature_mode"]
    n_bits = bundle["n_bits"]

    def _predict_mol(m: Chem.Mol) -> float:
        smi = Chem.MolToSmiles(m)
        X_m, _, _ = featurize_smiles_list([smi], feature_mode=feature_mode, n_bits=n_bits)
        if bundle["task_type"] == "classification" and hasattr(pipe, "predict_proba"):
            return float(pipe.predict_proba(X_m)[0, 1])
        return float(pipe.predict(X_m)[0])

    base_pred = _predict_mol(mol)

    # RDKit SimilarityMaps-style atom masking using Morgan fingerprint callback
    def _morgan_fp(m: Chem.Mol, atom_id: int) -> Any:
        return SimilarityMaps.GetMorganFingerprint(m, atomId=atom_id, radius=2, fpType="bv", nBits=n_bits)

    # Direct atom occlusion weights on the QSAR predictor (model-agnostic & chemically faithful)
    weights: list[float] = []
    n_atoms = mol.GetNumAtoms()
    for atom_idx in range(n_atoms):
        rw = Chem.RWMol(mol)
        atom = rw.GetAtomWithIdx(atom_idx)
        # Replace atom with dummy or change to Carbon/Hydrogen-like probe only if valid, else use bit contribution
        try:
            if atom.GetAtomicNum() != 6:
                atom.SetAtomicNum(6)
            else:
                atom.SetAtomicNum(7)
            Chem.SanitizeMol(rw)
            occ_pred = _predict_mol(rw.GetMol())
            weights.append(float(base_pred - occ_pred))
        except Exception:
            weights.append(0.0)

    # Normalize weights for visualization while keeping signs
    max_abs = max([abs(w) for w in weights] or [1.0])
    if max_abs > 1e-9:
        norm_weights = [w / max_abs for w in weights]
    else:
        norm_weights = weights

    rdDepictor.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    SimilarityMaps.GetSimilarityMapFromWeights(
        mol,
        norm_weights,
        draw2d=drawer,
        colorMap="PiYG",
        contourLines=6,
    )
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()

    return {
        "smiles": smiles,
        "predicted_value": round(base_pred, 4),
        "atom_weights": [round(float(w), 4) for w in norm_weights],
        "svg": svg,
    }
