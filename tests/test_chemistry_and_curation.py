"""Tests for Fourches et al. chemical curation, standardization, and descriptors."""

from pathlib import Path

import pandas as pd

from khemsar.chemistry.curation import CurationConfig, curate_bioactivity_dataset, standardize_molecule
from khemsar.chemistry.descriptors import featurize_smiles_list

DEMO_CSV = Path(__file__).resolve().parent.parent / "khemsar" / "data" / "demo_dataset.csv"


def test_standardize_molecule_filters_salts_and_inorganics() -> None:
    mol, can, ikey, reason = standardize_molecule("O=C([O-])Cc1ccccc1Nc1c(Cl)cccc1Cl.[Na+]")
    assert mol is not None and reason == ""
    assert "." not in can
    assert len(ikey) == 27

    mol_inorg, _, _, reason_inorg = standardize_molecule("[Na+].[Cl-]")
    assert mol_inorg is None
    assert reason_inorg == "inorganic_no_carbon"

    mol_mix, _, _, reason_mix = standardize_molecule("c1ccccc1N.c1ccc(C(=O)O)cc1")
    assert mol_mix is None
    assert reason_mix == "organic_mixture"


def test_demo_dataset_curation_regression_vs_classification() -> None:
    df = pd.read_csv(DEMO_CSV)
    res_reg = curate_bioactivity_dataset(df, CurationConfig(target_endpoint="IC50", task_type="regression"))
    rep = res_reg["report"]
    assert rep["raw_count"] == len(df)
    assert rep["excluded_censored_or_invalid_value"] == 1  # Ibuprofen_Censored ('>')
    assert rep["merged_duplicates"] >= 2  # Celecoxib_Rep and Diclofenac_NaSalt
    assert rep["final_count"] >= 42

    res_cls = curate_bioactivity_dataset(
        df, CurationConfig(target_endpoint="IC50", task_type="classification", activity_cutoff_pAct=6.0)
    )
    assert res_cls["report"]["excluded_censored_or_invalid_value"] == 0


def test_featurization_hybrid() -> None:
    X, names, profiles = featurize_smiles_list(
        ["Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1", "O=C(O)Cc1ccccc1Nc1c(Cl)cccc1Cl"],
        feature_mode="hybrid",
        n_bits=256,
    )
    assert X.shape == (2, 14 + 256)
    assert len(names) == 270
    assert 0.0 <= profiles[0]["QED"] <= 1.0
    assert 1.0 <= profiles[0]["SA_Score"] <= 10.0
