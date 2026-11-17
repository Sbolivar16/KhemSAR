"""OECD-compliant QSAR validation: Golbraikh-Tropsha, Q2F1/F2/F3, CCC, Y-scrambling, Williams Plot & k-NN AD."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.base import clone
from sklearn.decomposition import PCA
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler


def _concordance_correlation_coefficient(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mean_t = float(np.mean(y_true))
    mean_p = float(np.mean(y_pred))
    var_t = float(np.var(y_true))
    var_p = float(np.var(y_pred))
    cov = float(np.mean((y_true - mean_t) * (y_pred - mean_p)))
    denom = var_t + var_p + (mean_t - mean_p) ** 2
    return float((2.0 * cov) / denom) if denom > 1e-12 else 0.0


def compute_regression_metrics(
    y_train: np.ndarray,
    y_train_pred: np.ndarray,
    y_train_cv_pred: np.ndarray,
    y_test: np.ndarray,
    y_test_pred: np.ndarray,
) -> dict[str, Any]:
    """Compute paper-ready OECD / Golbraikh-Tropsha / Tropsha-Gramatica regression metrics."""
    r2_train = float(r2_score(y_train, y_train_pred))
    q2_cv = float(r2_score(y_train, y_train_cv_pred))
    rmse_cv = float(np.sqrt(mean_squared_error(y_train, y_train_cv_pred)))
    mae_cv = float(mean_absolute_error(y_train, y_train_cv_pred))

    r2_ext = float(r2_score(y_test, y_test_pred))
    rmse_ext = float(np.sqrt(mean_squared_error(y_test, y_test_pred)))
    mae_ext = float(mean_absolute_error(y_test, y_test_pred))
    ccc_ext = _concordance_correlation_coefficient(y_test, y_test_pred)

    train_mean = float(np.mean(y_train))
    test_mean = float(np.mean(y_test))
    press_ext = float(np.sum((y_test - y_test_pred) ** 2))

    tss_f1 = float(np.sum((y_test - train_mean) ** 2))
    tss_f2 = float(np.sum((y_test - test_mean) ** 2))
    tss_f3 = float(np.sum((y_train - train_mean) ** 2))

    q2_f1 = 1.0 - (press_ext / tss_f1) if tss_f1 > 1e-12 else 0.0
    q2_f2 = 1.0 - (press_ext / tss_f2) if tss_f2 > 1e-12 else 0.0
    q2_f3 = 1.0 - ((press_ext / len(y_test)) / (tss_f3 / len(y_train))) if tss_f3 > 1e-12 else 0.0

    # Golbraikh-Tropsha criteria on external test set
    denom_k = float(np.sum(y_test_pred**2))
    denom_kp = float(np.sum(y_test**2))
    k = float(np.sum(y_test * y_test_pred) / denom_k) if denom_k > 1e-12 else 0.0
    kp = float(np.sum(y_test * y_test_pred) / denom_kp) if denom_kp > 1e-12 else 0.0

    y_hat_0 = k * y_test_pred
    y_0 = kp * y_test
    r0_sq = 1.0 - (float(np.sum((y_test - y_hat_0) ** 2)) / tss_f2) if tss_f2 > 1e-12 else 0.0
    pred_mean = float(np.mean(y_test_pred))
    tss_pred = float(np.sum((y_test_pred - pred_mean) ** 2))
    rp0_sq = 1.0 - (float(np.sum((y_test_pred - y_0) ** 2)) / tss_pred) if tss_pred > 1e-12 else 0.0

    corr = float(np.corrcoef(y_test, y_test_pred)[0, 1]) if (np.std(y_test) > 1e-9 and np.std(y_test_pred) > 1e-9) else 0.0
    r_sq_pearson = corr**2
    rel_r0 = ((r_sq_pearson - r0_sq) / r_sq_pearson) if r_sq_pearson > 1e-12 else 1.0
    rel_rp0 = ((r_sq_pearson - rp0_sq) / r_sq_pearson) if r_sq_pearson > 1e-12 else 1.0

    gt_pass = (
        q2_cv > 0.5
        and r_sq_pearson > 0.6
        and (0.85 <= k <= 1.15 or 0.85 <= kp <= 1.15)
        and (rel_r0 < 0.1 or rel_rp0 < 0.1)
        and abs(r0_sq - rp0_sq) < 0.3
    )

    return {
        "R2_train": round(r2_train, 4),
        "Q2_CV": round(q2_cv, 4),
        "RMSE_CV": round(rmse_cv, 4),
        "MAE_CV": round(mae_cv, 4),
        "R2_ext": round(r2_ext, 4),
        "R2_pearson_ext": round(r_sq_pearson, 4),
        "Q2_F1": round(float(q2_f1), 4),
        "Q2_F2": round(float(q2_f2), 4),
        "Q2_F3": round(float(q2_f3), 4),
        "CCC_ext": round(ccc_ext, 4),
        "RMSE_ext": round(rmse_ext, 4),
        "MAE_ext": round(mae_ext, 4),
        "k": round(k, 4),
        "k_prime": round(kp, 4),
        "R0_sq": round(float(r0_sq), 4),
        "R0_prime_sq": round(float(rp0_sq), 4),
        "Golbraikh_Tropsha_pass": bool(gt_pass),
    }


def compute_classification_metrics(
    y_train: np.ndarray,
    y_train_cv_pred: np.ndarray,
    y_test: np.ndarray,
    y_test_pred: np.ndarray,
    y_test_prob: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute paper-ready binary classification QSAR metrics."""
    mcc_cv = float(matthews_corrcoef(y_train, y_train_cv_pred))
    bacc_cv = float(balanced_accuracy_score(y_train, y_train_cv_pred))

    mcc_ext = float(matthews_corrcoef(y_test, y_test_pred))
    bacc_ext = float(balanced_accuracy_score(y_test, y_test_pred))
    acc_ext = float(accuracy_score(y_test, y_test_pred))
    f1_ext = float(f1_score(y_test, y_test_pred, zero_division=0))
    kappa_ext = float(cohen_kappa_score(y_test, y_test_pred))

    cm = confusion_matrix(y_test, y_test_pred, labels=[0, 1])
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]
    sens = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    roc_auc = None
    pr_auc = None
    if y_test_prob is not None and len(np.unique(y_test)) > 1:
        try:
            roc_auc = round(float(roc_auc_score(y_test, y_test_prob)), 4)
            pr_auc = round(float(average_precision_score(y_test, y_test_prob)), 4)
        except Exception:
            pass

    return {
        "MCC_CV": round(mcc_cv, 4),
        "Balanced_Accuracy_CV": round(bacc_cv, 4),
        "MCC_ext": round(mcc_ext, 4),
        "Balanced_Accuracy_ext": round(bacc_ext, 4),
        "Accuracy_ext": round(acc_ext, 4),
        "F1_ext": round(f1_ext, 4),
        "Cohen_Kappa_ext": round(kappa_ext, 4),
        "Sensitivity_ext": round(float(sens), 4),
        "Specificity_ext": round(float(spec), 4),
        "ROC_AUC_ext": roc_auc,
        "PR_AUC_ext": pr_auc,
        "Confusion_Matrix": {"TN": tn, "FP": fp, "FN": fn, "TP": tp},
    }


def compute_crp2(r2_real: float, r2_scrambled_mean: float) -> float:
    """Compute Rücker et al. (2007) / Todeschini cRp2 = R * sqrt(max(0, R^2 - R^2_perm_mean))."""
    if r2_real <= 0.0:
        return 0.0
    diff = max(0.0, float(r2_real) - float(r2_scrambled_mean))
    return float(np.sqrt(float(r2_real)) * np.sqrt(diff))


def run_y_scrambling(
    estimator: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    task_type: str = "regression",
    n_permutations: int = 50,
    cv_folds: int = 5,
    random_state: int = 42,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Perform Y-scrambling robustness check and compute Rücker/Todeschini cRp2."""
    rng = np.random.default_rng(random_state)
    n_folds = min(3, cv_folds, max(2, len(y_train) // 4))

    if task_type == "classification":
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    else:
        cv = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)

    base_model = clone(estimator)
    base_model.fit(X_train, y_train)
    base_train_pred = base_model.predict(X_train)
    try:
        base_cv_pred = cross_val_predict(clone(estimator), X_train, y_train, cv=cv)
    except Exception:
        base_cv_pred = base_train_pred

    if task_type == "classification":
        base_score = float(matthews_corrcoef(y_train, base_train_pred))
        base_cv_score = float(matthews_corrcoef(y_train, base_cv_pred))
    else:
        base_score = float(r2_score(y_train, base_train_pred))
        base_cv_score = float(r2_score(y_train, base_cv_pred))

    scrambled_r2: list[float] = []
    scrambled_q2: list[float] = []
    y_corrs: list[float] = []

    for perm_idx in range(1, n_permutations + 1):
        if progress_cb and (perm_idx == 1 or perm_idx % max(1, n_permutations // 8) == 0 or perm_idx == n_permutations):
            progress_cb(70 + int(22 * (perm_idx / max(1, n_permutations))), f"Y-Scrambling ({perm_idx}/{n_permutations})...")
        y_perm = rng.permutation(y_train)
        corr = float(abs(np.corrcoef(y_train, y_perm)[0, 1])) if np.std(y_perm) > 1e-9 else 0.0
        y_corrs.append(round(corr, 4))
        m = clone(estimator)
        m.fit(X_train, y_perm)
        pred_tr = m.predict(X_train)
        try:
            pred_cv = cross_val_predict(clone(estimator), X_train, y_perm, cv=cv)
        except Exception:
            pred_cv = pred_tr

        if task_type == "classification":
            scrambled_r2.append(round(float(matthews_corrcoef(y_perm, pred_tr)), 4))
            scrambled_q2.append(round(float(matthews_corrcoef(y_perm, pred_cv)), 4))
        else:
            scrambled_r2.append(round(float(r2_score(y_perm, pred_tr)), 4))
            scrambled_q2.append(round(float(r2_score(y_perm, pred_cv)), 4))

    mean_scram_r2 = float(np.mean(scrambled_r2))
    mean_scram_q2 = float(np.mean(scrambled_q2))
    crp2 = compute_crp2(base_score, max(0.0, mean_scram_r2))

    return {
        "n_permutations": n_permutations,
        "random_state": int(random_state),
        "original_R2_or_MCC": round(base_score, 4),
        "original_Q2_CV": round(base_cv_score, 4),
        "scrambled_mean": round(mean_scram_r2, 4),
        "scrambled_q2_mean": round(mean_scram_q2, 4),
        "cRp2": round(crp2, 4),
        "passes_chance_correlation_check": bool(
            crp2 > 0.5 or (task_type == "classification" and base_cv_score > mean_scram_q2 + 0.2)
        ),
        "points": [
            {"y_corr": c, "r2_scrambled": r, "q2_scrambled": q}
            for c, r, q in zip(y_corrs, scrambled_r2, scrambled_q2)
        ],
    }


def compute_williams_plot_and_ad(
    X_train: np.ndarray,
    y_train: np.ndarray,
    y_train_pred: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    y_test_pred: np.ndarray,
    smiles_train: list[str],
    smiles_test: list[str],
) -> dict[str, Any]:
    """Compute Williams Plot (Leverage vs Standardized Residuals) and Tanimoto k-NN Applicability Domain."""
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(np.nan_to_num(X_train, nan=0.0))
    X_te_s = scaler.transform(np.nan_to_num(X_test, nan=0.0))

    # Project onto well-conditioned orthogonal latent components when p is large relative to n
    n_tr, p_raw = X_tr_s.shape
    max_comp = max(2, min(n_tr // 3, p_raw, 12))
    pca = PCA(n_components=max_comp, random_state=42)
    Z_tr = pca.fit_transform(X_tr_s)
    Z_te = pca.transform(X_te_s)

    # Add intercept column for leverage matrix
    Z_tr_aug = np.hstack([np.ones((Z_tr.shape[0], 1)), Z_tr])
    Z_te_aug = np.hstack([np.ones((Z_te.shape[0], 1)), Z_te])
    p_eff = Z_tr_aug.shape[1]

    pinv_xtx = np.linalg.pinv(Z_tr_aug.T @ Z_tr_aug + 1e-6 * np.eye(p_eff))
    h_train = np.einsum("ij,jk,ik->i", Z_tr_aug, pinv_xtx, Z_tr_aug)
    h_test = np.einsum("ij,jk,ik->i", Z_te_aug, pinv_xtx, Z_te_aug)
    h_star = float((3.0 * p_eff) / max(1, n_tr))

    res_train = y_train - y_train_pred
    res_test = y_test - y_test_pred
    std_res = float(np.std(res_train, ddof=1)) if len(res_train) > 1 else 1.0
    std_res = max(std_res, 1e-6)
    z_res_train = res_train / std_res
    z_res_test = res_test / std_res

    # Tanimoto k-NN similarity (k=3) AD
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    fps_tr = [gen.GetFingerprint(Chem.MolFromSmiles(s)) for s in smiles_train if Chem.MolFromSmiles(s) is not None]

    def _knn_sim(smi: str) -> float:
        mol = Chem.MolFromSmiles(smi)
        if mol is None or not fps_tr:
            return 0.0
        fp = gen.GetFingerprint(mol)
        sims = sorted(DataStructs.BulkTanimotoSimilarity(fp, fps_tr), reverse=True)
        top = sims[: min(3, len(sims))]
        return float(np.mean(top))

    knn_test = [_knn_sim(s) for s in smiles_test]
    # Training internal similarity threshold (mean - 1.5 * std, bounded in [0.25, 0.70])
    tr_self_sims: list[float] = []
    for i, fp in enumerate(fps_tr):
        sims = DataStructs.BulkTanimotoSimilarity(fp, fps_tr)
        others = sorted([s for j, s in enumerate(sims) if j != i], reverse=True)
        if others:
            tr_self_sims.append(float(np.mean(others[: min(3, len(others))])))
    sim_thresh = float(np.clip(np.mean(tr_self_sims) - 1.5 * np.std(tr_self_sims), 0.25, 0.70)) if tr_self_sims else 0.35

    train_points = [
        {
            "smiles": smiles_train[i],
            "leverage": round(float(h_train[i]), 4),
            "std_residual": round(float(z_res_train[i]), 4),
            "in_ad": bool(h_train[i] <= h_star and abs(z_res_train[i]) <= 3.0),
            "split": "train",
        }
        for i in range(len(smiles_train))
    ]
    test_points = [
        {
            "smiles": smiles_test[i],
            "leverage": round(float(h_test[i]), 4),
            "std_residual": round(float(z_res_test[i]), 4),
            "knn_tanimoto": round(float(knn_test[i]), 4),
            "in_leverage_ad": bool(h_test[i] <= h_star and abs(z_res_test[i]) <= 3.0),
            "in_similarity_ad": bool(knn_test[i] >= sim_thresh),
            "in_ad": bool(h_test[i] <= h_star and abs(z_res_test[i]) <= 3.0),
            "split": "test",
        }
        for i in range(len(smiles_test))
    ]

    in_ad_pct = (
        100.0 * sum(1 for pt in test_points if pt["in_ad"]) / max(1, len(test_points))
    )

    return {
        "h_star": round(h_star, 4),
        "residual_cutoff": 3.0,
        "tanimoto_threshold": round(sim_thresh, 4),
        "test_coverage_pct": round(in_ad_pct, 2),
        "n_test_outliers": sum(1 for pt in test_points if not pt["in_ad"]),
        "train_points": train_points,
        "test_points": test_points,
        "pca_model": pca,
        "scaler": scaler,
        "pinv_xtx": pinv_xtx,
        "fps_train": fps_tr,
    }
