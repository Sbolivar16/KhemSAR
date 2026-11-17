"""QSAR model training, nested hyperparameter tuning, model comparison, and prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import joblib
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.model_selection import GridSearchCV, KFold, StratifiedKFold, cross_val_predict
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR

from khemsar.chemistry.descriptors import featurize_smiles_list
from khemsar.qsar.splitting import split_dataset
from khemsar.qsar.validation import (
    compute_classification_metrics,
    compute_regression_metrics,
    compute_williams_plot_and_ad,
    run_y_scrambling,
)

# Optional gradient boosting engines (gracefully skipped if native OpenMP lib is unavailable)
XGBRegressor = None
XGBClassifier = None
try:
    from xgboost import XGBClassifier as _XGBClassifier
    from xgboost import XGBRegressor as _XGBRegressor

    XGBRegressor = _XGBRegressor
    XGBClassifier = _XGBClassifier
except Exception:
    pass

LGBMRegressor = None
LGBMClassifier = None
try:
    from lightgbm import LGBMClassifier as _LGBMClassifier
    from lightgbm import LGBMRegressor as _LGBMRegressor

    LGBMRegressor = _LGBMRegressor
    LGBMClassifier = _LGBMClassifier
except Exception:
    pass


@dataclass
class QSARTrainConfig:
    task_type: str = "regression"  # regression | classification
    feature_mode: str = "hybrid"  # physchem | morgan_ecfp4 | maccs | hybrid
    n_bits: int = 512
    split_method: str = "scaffold"  # scaffold | kennard_stone | temporal | stratified
    test_size: float = 0.2
    cv_folds: int = 5
    y_scrambling_permutations: int = 50
    random_state: int = 42
    algorithms: list[str] | None = None


def _build_candidate_specs(task_type: str, random_state: int) -> dict[str, tuple[Any, dict[str, Any]]]:
    if task_type == "classification":
        specs: dict[str, tuple[Any, dict[str, Any]]] = {
            "LogisticRegression": (
                LogisticRegression(max_iter=1500, class_weight="balanced", random_state=random_state),
                {"model__C": [0.1, 1.0, 10.0]},
            ),
            "RandomForest": (
                RandomForestClassifier(class_weight="balanced", random_state=random_state),
                {"model__n_estimators": [150, 300], "model__max_depth": [None, 10]},
            ),
            "ExtraTrees": (
                ExtraTreesClassifier(class_weight="balanced", random_state=random_state),
                {"model__n_estimators": [150, 300], "model__max_depth": [None, 10]},
            ),
            "HistGradientBoosting": (
                HistGradientBoostingClassifier(random_state=random_state),
                {"model__max_depth": [4, 7], "model__learning_rate": [0.05, 0.1]},
            ),
            "SVC": (
                SVC(probability=True, class_weight="balanced", random_state=random_state),
                {"model__C": [0.5, 2.0, 10.0], "model__gamma": ["scale"]},
            ),
            "MLP": (
                MLPClassifier(max_iter=600, early_stopping=True, random_state=random_state),
                {"model__hidden_layer_sizes": [(64, 32), (128,)]},
            ),
        }
        if XGBClassifier is not None:
            specs["XGBoost"] = (
                XGBClassifier(random_state=random_state, eval_metric="logloss"),
                {"model__n_estimators": [120, 220], "model__max_depth": [3, 5]},
            )
        if LGBMClassifier is not None:
            specs["LightGBM"] = (
                LGBMClassifier(random_state=random_state, verbose=-1),
                {"model__n_estimators": [120, 220], "model__max_depth": [4, 6]},
            )
        return specs

    specs = {
        "PLS": (
            PLSRegression(),
            {"model__n_components": [2, 4, 6]},
        ),
        "Ridge": (
            Ridge(random_state=random_state),
            {"model__alpha": [0.1, 1.0, 10.0, 50.0]},
        ),
        "ElasticNet": (
            ElasticNet(max_iter=3000, random_state=random_state),
            {"model__alpha": [0.01, 0.1, 1.0], "model__l1_ratio": [0.2, 0.5, 0.8]},
        ),
        "RandomForest": (
            RandomForestRegressor(random_state=random_state),
            {"model__n_estimators": [150, 300], "model__max_depth": [None, 10]},
        ),
        "ExtraTrees": (
            ExtraTreesRegressor(random_state=random_state),
            {"model__n_estimators": [150, 300], "model__max_depth": [None, 10]},
        ),
        "HistGradientBoosting": (
            HistGradientBoostingRegressor(random_state=random_state),
            {"model__max_depth": [4, 7], "model__learning_rate": [0.05, 0.1]},
        ),
        "SVR": (
            SVR(),
            {"model__C": [1.0, 5.0, 20.0], "model__epsilon": [0.1, 0.25]},
        ),
        "MLP": (
            MLPRegressor(max_iter=600, early_stopping=True, random_state=random_state),
            {"model__hidden_layer_sizes": [(64, 32), (128,)]},
        ),
    }
    if XGBRegressor is not None:
        specs["XGBoost"] = (
            XGBRegressor(random_state=random_state),
            {"model__n_estimators": [120, 220], "model__max_depth": [3, 5]},
        )
    if LGBMRegressor is not None:
        specs["LightGBM"] = (
            LGBMRegressor(random_state=random_state, verbose=-1),
            {"model__n_estimators": [120, 220], "model__max_depth": [4, 6]},
        )
    return specs


def train_and_validate_qsar(
    curated_records: list[dict[str, Any]],
    config: QSARTrainConfig | None = None,
    artifact_path: str | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Run full OECD-compliant QSAR training, validation, Y-scrambling, and AD analysis."""
    cfg = config or QSARTrainConfig()
    if len(curated_records) < 12:
        raise ValueError("At least 12 curated compounds are required for QSAR training & validation.")

    if progress_cb:
        progress_cb(5, f"Computing descriptors ({cfg.feature_mode}) for {len(curated_records)} molecules...")
    smiles_list = [r["smiles"] for r in curated_records]
    years = [r.get("year") for r in curated_records]
    y = np.asarray(
        [int(r["active"]) if cfg.task_type == "classification" else float(r["pActivity"]) for r in curated_records]
    )

    X, feature_names, profiles = featurize_smiles_list(
        smiles_list, feature_mode=cfg.feature_mode, n_bits=cfg.n_bits
    )
    if progress_cb:
        progress_cb(12, f"Splitting dataset ({cfg.split_method})...")
    train_idx, test_idx, actual_split = split_dataset(
        smiles_list=smiles_list,
        y=y,
        X=X,
        years=years,
        method=cfg.split_method,
        test_size=cfg.test_size,
        task_type=cfg.task_type,
        random_state=cfg.random_state,
    )

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    smiles_train = [smiles_list[i] for i in train_idx]
    smiles_test = [smiles_list[i] for i in test_idx]

    n_folds = min(cfg.cv_folds, max(2, len(y_train) // 4))
    if cfg.task_type == "classification":
        min_cls = int(min(np.sum(y_train == 0), np.sum(y_train == 1)))
        n_folds = max(2, min(n_folds, min_cls))
        outer_cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=cfg.random_state)
        inner_cv = StratifiedKFold(n_splits=max(2, min(3, n_folds)), shuffle=True, random_state=cfg.random_state)
        scoring = "balanced_accuracy"
    else:
        outer_cv = KFold(n_splits=n_folds, shuffle=True, random_state=cfg.random_state)
        inner_cv = KFold(n_splits=max(2, min(3, n_folds)), shuffle=True, random_state=cfg.random_state)
        scoring = "r2"

    all_specs = _build_candidate_specs(cfg.task_type, cfg.random_state)
    selected_algos = cfg.algorithms or [
        k for k in ("PLS", "Ridge", "RandomForest", "ExtraTrees", "HistGradientBoosting", "SVR", "XGBoost") if k in all_specs
    ]
    if cfg.task_type == "classification" and not cfg.algorithms:
        selected_algos = [
            k for k in ("LogisticRegression", "RandomForest", "ExtraTrees", "HistGradientBoosting", "SVC", "XGBoost") if k in all_specs
        ]

    leaderboard: list[dict[str, Any]] = []
    best_entry: dict[str, Any] | None = None
    best_pipeline: Pipeline | None = None

    total_algos = max(1, len(selected_algos))
    for algo_i, algo_name in enumerate(selected_algos, start=1):
        if algo_name not in all_specs:
            continue
        if progress_cb:
            progress_cb(15 + int(53 * ((algo_i - 1) / total_algos)), f"Training {algo_name} ({algo_i}/{total_algos})...")
        est, param_grid = all_specs[algo_name]
        # Adapt PLS max components to training size/features
        if algo_name == "PLS":
            max_comp = max(1, min(6, X_train.shape[0] // 4, X_train.shape[1] - 1))
            param_grid = {"model__n_components": sorted(set([1, min(2, max_comp), min(4, max_comp), max_comp]))}

        pipe = Pipeline(
            [
                ("var", VarianceThreshold(threshold=0.0)),
                ("scaler", StandardScaler()),
                ("model", est),
            ]
        )
        try:
            gs = GridSearchCV(pipe, param_grid=param_grid, cv=inner_cv, scoring=scoring, n_jobs=1, error_score="raise")
            gs.fit(X_train, y_train)
            best_est = gs.best_estimator_

            y_tr_pred = np.asarray(best_est.predict(X_train)).ravel()
            y_tr_cv_pred = np.asarray(cross_val_predict(best_est, X_train, y_train, cv=outer_cv, n_jobs=1)).ravel()
            y_te_pred = np.asarray(best_est.predict(X_test)).ravel()

            if cfg.task_type == "classification":
                y_te_prob = (
                    best_est.predict_proba(X_test)[:, 1]
                    if hasattr(best_est, "predict_proba")
                    else None
                )
                metrics = compute_classification_metrics(y_train, y_tr_cv_pred, y_test, y_te_pred, y_te_prob)
                rank_score = metrics["MCC_CV"]
            else:
                metrics = compute_regression_metrics(y_train, y_tr_pred, y_tr_cv_pred, y_test, y_te_pred)
                rank_score = metrics["Q2_CV"]

            entry = {
                "algorithm": algo_name,
                "best_params": gs.best_params_,
                "metrics": metrics,
                "rank_score": rank_score,
                "y_train_pred": [round(float(v), 4) for v in y_tr_pred],
                "y_train_cv_pred": [round(float(v), 4) for v in y_tr_cv_pred],
                "y_test_pred": [round(float(v), 4) for v in y_te_pred],
            }
            leaderboard.append(entry)
            if best_entry is None or rank_score > best_entry["rank_score"]:
                best_entry = entry
                best_pipeline = best_est
        except Exception as exc:
            leaderboard.append({"algorithm": algo_name, "error": str(exc), "rank_score": -999.0, "metrics": {}})

    if best_entry is None or best_pipeline is None:
        raise RuntimeError("All candidate QSAR algorithms failed to train.")

    leaderboard.sort(key=lambda item: item.get("rank_score", -999.0), reverse=True)

    y_scrambling = run_y_scrambling(
        best_pipeline,
        X_train,
        y_train,
        task_type=cfg.task_type,
        n_permutations=cfg.y_scrambling_permutations,
        cv_folds=n_folds,
        random_state=cfg.random_state,
        progress_cb=progress_cb,
    )

    if progress_cb:
        progress_cb(95, "Computing Williams Plot & Tanimoto Applicability Domain...")

    y_tr_pred_best = np.asarray(best_entry["y_train_pred"], dtype=float)
    y_te_pred_best = np.asarray(best_entry["y_test_pred"], dtype=float)
    ad_result = compute_williams_plot_and_ad(
        X_train=X_train,
        y_train=y_train.astype(float),
        y_train_pred=y_tr_pred_best,
        X_test=X_test,
        y_test=y_test.astype(float),
        y_test_pred=y_te_pred_best,
        smiles_train=smiles_train,
        smiles_test=smiles_test,
    )

    # Save trained bundle for later predictions, SHAP & de novo scoring
    bundle = {
        "pipeline": best_pipeline,
        "task_type": cfg.task_type,
        "feature_mode": cfg.feature_mode,
        "n_bits": cfg.n_bits,
        "feature_names": feature_names,
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "smiles_train": smiles_train,
        "smiles_test": smiles_test,
        "ad_scaler": ad_result.pop("scaler"),
        "ad_pca": ad_result.pop("pca_model"),
        "ad_pinv_xtx": ad_result.pop("pinv_xtx"),
        "ad_h_star": ad_result["h_star"],
        "ad_tanimoto_threshold": ad_result["tanimoto_threshold"],
        "ad_fps_train": ad_result.pop("fps_train"),
    }
    if artifact_path:
        joblib.dump(bundle, artifact_path)

    linear_fit: dict[str, Any] = {}
    if cfg.task_type == "regression" and len(y_train) >= 2 and len(y_test) >= 2:
        y_cv_arr = np.asarray(best_entry["y_train_cv_pred"], dtype=float)
        y_te_arr = np.asarray(best_entry["y_test_pred"], dtype=float)
        if np.std(y_train) > 1e-8:
            m_tr, b_tr = np.polyfit(y_train.astype(float), y_cv_arr, 1)
            linear_fit["train_cv"] = {"slope": round(float(m_tr), 4), "intercept": round(float(b_tr), 4)}
        if np.std(y_test) > 1e-8:
            m_te, b_te = np.polyfit(y_test.astype(float), y_te_arr, 1)
            linear_fit["test_ext"] = {"slope": round(float(m_te), 4), "intercept": round(float(b_te), 4)}

    return {
        "task_type": cfg.task_type,
        "feature_mode": cfg.feature_mode,
        "split_method_requested": cfg.split_method,
        "split_method_used": actual_split,
        "n_total": len(curated_records),
        "n_train": int(len(train_idx)),
        "n_test": int(len(test_idx)),
        "best_algorithm": best_entry["algorithm"],
        "best_params": best_entry["best_params"],
        "best_metrics": best_entry["metrics"],
        "linear_fit": linear_fit,
        "leaderboard": [
            {"algorithm": x["algorithm"], "metrics": x.get("metrics", {}), "best_params": x.get("best_params", {}), "error": x.get("error", "")}
            for x in leaderboard
        ],
        "predictions": {
            "train": [
                {
                    "compound_id": curated_records[i]["compound_id"],
                    "name": curated_records[i]["name"],
                    "smiles": curated_records[i]["smiles"],
                    "y_true": float(y_train[k]),
                    "y_pred": float(best_entry["y_train_pred"][k]),
                    "y_cv_pred": float(best_entry["y_train_cv_pred"][k]),
                }
                for k, i in enumerate(train_idx)
            ],
            "test": [
                {
                    "compound_id": curated_records[i]["compound_id"],
                    "name": curated_records[i]["name"],
                    "smiles": curated_records[i]["smiles"],
                    "y_true": float(y_test[k]),
                    "y_pred": float(best_entry["y_test_pred"][k]),
                }
                for k, i in enumerate(test_idx)
            ],
        },
        "y_scrambling": y_scrambling,
        "applicability_domain": ad_result,
        "medchem_summary": profiles[:10],
        "artifact_path": artifact_path or "",
    }


def predict_with_qsar_bundle(bundle: dict[str, Any], smiles_list: list[str]) -> list[dict[str, Any]]:
    """Predict bioactivity/class and Applicability Domain membership for new molecules."""
    X_new, _, profiles = featurize_smiles_list(
        smiles_list,
        feature_mode=bundle["feature_mode"],
        n_bits=bundle["n_bits"],
    )
    pipe = bundle["pipeline"]
    preds = np.asarray(pipe.predict(X_new)).ravel()
    probs = pipe.predict_proba(X_new)[:, 1] if (bundle["task_type"] == "classification" and hasattr(pipe, "predict_proba")) else None

    Z_new = bundle["ad_pca"].transform(bundle["ad_scaler"].transform(np.nan_to_num(X_new, nan=0.0)))
    Z_aug = np.hstack([np.ones((Z_new.shape[0], 1)), Z_new])
    h_new = np.einsum("ij,jk,ik->i", Z_aug, bundle["ad_pinv_xtx"], Z_aug)

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    fps_tr = bundle["ad_fps_train"]

    results: list[dict[str, Any]] = []
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(smi)
        knn_sim = 0.0
        if mol is not None and fps_tr:
            fp = gen.GetFingerprint(mol)
            sims = sorted(DataStructs.BulkTanimotoSimilarity(fp, fps_tr), reverse=True)
            knn_sim = float(np.mean(sims[: min(3, len(sims))]))
        in_lev = bool(h_new[i] <= bundle["ad_h_star"])
        in_sim = bool(knn_sim >= bundle["ad_tanimoto_threshold"])
        results.append(
            {
                "smiles": smi,
                "predicted_value": round(float(preds[i]), 4),
                "predicted_prob": round(float(probs[i]), 4) if probs is not None else None,
                "leverage": round(float(h_new[i]), 4),
                "h_star": bundle["ad_h_star"],
                "knn_tanimoto": round(knn_sim, 4),
                "in_ad": bool(in_lev and in_sim),
                "in_leverage_ad": in_lev,
                "in_similarity_ad": in_sim,
                "medchem": profiles[i],
            }
        )
    return results
