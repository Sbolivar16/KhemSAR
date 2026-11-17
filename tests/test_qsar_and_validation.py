"""Tests for QSAR splitting, OECD modeling, Golbraikh-Tropsha, Y-scrambling, and Williams AD."""

from pathlib import Path

import numpy as np
import pandas as pd

from khemsar.chemistry.curation import CurationConfig, curate_bioactivity_dataset
from khemsar.qsar.modeling import QSARTrainConfig, predict_with_qsar_bundle, train_and_validate_qsar
from khemsar.qsar.splitting import split_dataset

DEMO_CSV = Path(__file__).resolve().parent.parent / "khemsar" / "data" / "demo_dataset.csv"


def _curated_demo(task_type: str = "regression") -> list[dict]:
    df = pd.read_csv(DEMO_CSV)
    return curate_bioactivity_dataset(df, CurationConfig(target_endpoint="IC50", task_type=task_type))["curated_records"]


def test_splitting_methods() -> None:
    records = _curated_demo()
    smiles = [r["smiles"] for r in records]
    y = np.array([r["pActivity"] for r in records])
    years = [r.get("year") for r in records]

    for method in ("scaffold", "kennard_stone", "temporal", "stratified"):
        tr, te, used = split_dataset(smiles, y, X=np.random.default_rng(0).normal(size=(len(smiles), 8)), years=years, method=method)
        assert len(tr) + len(te) == len(smiles)
        assert set(tr).isdisjoint(set(te))
        assert used in ("scaffold", "kennard_stone", "temporal", "stratified")


def test_qsar_regression_and_prediction(tmp_path: Path) -> None:
    records = _curated_demo("regression")
    bundle_path = tmp_path / "qsar_bundle.joblib"
    res = train_and_validate_qsar(
        records,
        QSARTrainConfig(
            task_type="regression",
            feature_mode="hybrid",
            n_bits=256,
            split_method="stratified",
            y_scrambling_permutations=15,
            algorithms=["Ridge", "RandomForest"],
        ),
        artifact_path=str(bundle_path),
    )
    assert bundle_path.exists()
    assert "Q2_CV" in res["best_metrics"]
    assert "Q2_F1" in res["best_metrics"]
    assert "CCC_ext" in res["best_metrics"]
    assert res["y_scrambling"]["n_permutations"] == 15
    assert res["applicability_domain"]["h_star"] > 0

    import joblib

    bundle = joblib.load(bundle_path)
    preds = predict_with_qsar_bundle(bundle, ["Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1"])
    assert len(preds) == 1
    assert isinstance(preds[0]["in_ad"], bool)


def test_qsar_classification() -> None:
    records = _curated_demo("classification")
    res = train_and_validate_qsar(
        records,
        QSARTrainConfig(
            task_type="classification",
            feature_mode="physchem",
            split_method="stratified",
            y_scrambling_permutations=10,
            algorithms=["LogisticRegression", "RandomForest"],
        ),
    )
    assert "MCC_ext" in res["best_metrics"]
    assert "ROC_AUC_ext" in res["best_metrics"]
