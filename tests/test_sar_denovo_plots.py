"""Tests for SAR (SALI, MMP, R-Group, SHAP, Atomic Maps), De Novo bioisosteres, 3D prep & paper figures."""

from pathlib import Path

import joblib
import pandas as pd

from khemsar.chemistry.curation import CurationConfig, curate_bioactivity_dataset
from khemsar.connectors.rcsb_pdb import prepare_receptor_and_docking_box
from khemsar.denovo.bioisosteres import apply_bioisosteric_replacements
from khemsar.denovo.generator import generate_denovo_candidates
from khemsar.denovo.prep_3d import export_docking_md_library
from khemsar.plots.paper_figures import generate_all_paper_figures
from khemsar.qsar.modeling import QSARTrainConfig, train_and_validate_qsar
from khemsar.sar.activity_cliffs import compute_activity_cliffs_and_space
from khemsar.sar.interpretability import compute_shap_importance, generate_atomic_attribution_svg
from khemsar.sar.mmp import analyze_matched_molecular_pairs
from khemsar.sar.rgroup import decompose_rgroups

DEMO_CSV = Path(__file__).resolve().parent.parent / "khemsar" / "data" / "demo_dataset.csv"


def test_sar_denovo_3d_and_plots(tmp_path: Path) -> None:
    df = pd.read_csv(DEMO_CSV)
    records = curate_bioactivity_dataset(df, CurationConfig(target_endpoint="IC50", task_type="regression"))["curated_records"]

    bundle_path = tmp_path / "bundle.joblib"
    qsar_res = train_and_validate_qsar(
        records,
        QSARTrainConfig(
            feature_mode="physchem",
            split_method="stratified",
            y_scrambling_permutations=10,
            algorithms=["RandomForest"],
        ),
        artifact_path=str(bundle_path),
    )
    bundle = joblib.load(bundle_path)

    cliffs = compute_activity_cliffs_and_space(records, similarity_cutoff=0.55, delta_p_cutoff=1.0)
    assert cliffs["n_cliffs_found"] >= 1
    assert len(cliffs["space_points"]) == len(records)

    mmp = analyze_matched_molecular_pairs(records)
    assert mmp["n_pairs"] >= 1

    rgroup = decompose_rgroups(records, core_smarts="c1cc(S(N)(=O)=O)ccc1")
    assert rgroup["matched_count"] >= 5

    shap_res = compute_shap_importance(bundle)
    assert len(shap_res["top_features"]) >= 3

    amap = generate_atomic_attribution_svg(bundle, records[0]["smiles"])
    assert "<svg" in amap["svg"]

    # Bioisostere transforms
    variants = apply_bioisosteric_replacements("O=C(O)Cc1ccccc1Nc1c(Cl)cccc1Cl")
    assert any(v["rule_id"] == "COOH_to_Tetrazole" for v in variants)

    denovo = generate_denovo_candidates(
        curated_records=records,
        qsar_bundle=bundle,
        mmp_transforms=mmp["transforms"],
        n_top_seeds=4,
        n_brics_samples=10,
        max_candidates=10,
    )
    assert denovo["n_generated"] >= 3

    # Minimal synthetic PDB receptor + co-crystal ligand check
    sample_pdb = (
        "ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C\n"
        "ATOM      2  CA  GLY A   2      12.000  11.000  10.500  1.00 20.00           C\n"
        "HETATM    3  C1  CEL A 500      20.000  21.000  22.000  1.00 15.00           C\n"
        "HETATM    4  S1  CEL A 500      22.000  23.000  24.000  1.00 15.00           S\n"
        "HETATM    5  O   HOH A 900       1.000   1.000   1.000  1.00 30.00           O\n"
        "END\n"
    )
    pdb_prep = prepare_receptor_and_docking_box(sample_pdb)
    assert pdb_prep["protein_atom_count"] == 2
    assert pdb_prep["docking_box"]["center_x"] == 21.0

    out_3d = export_docking_md_library(
        candidates=denovo["candidates"][:4],
        output_dir=tmp_path / "docking_ready",
        receptor_pdb=pdb_prep["receptor_pdb"],
        cocrystal_ligand_pdb=pdb_prep["cocrystal_ligand_pdb"],
        docking_box=pdb_prep["docking_box"],
    )
    assert out_3d["n_3d_embedded"] == 4
    assert Path(out_3d["files"]["sdf_3d"]).exists()
    assert Path(out_3d["files"]["xlsx"]).exists()
    assert Path(out_3d["files"]["vina_config"]).exists()

    figs = generate_all_paper_figures(
        output_dir=tmp_path / "plots",
        qsar_result=qsar_res,
        sar_result=cliffs,
        shap_result=shap_res,
        denovo_result=denovo,
        plot_lang="en",
        dpi=150,
    )
    assert "qsar_parity" in figs and Path(figs["qsar_parity"]["svg"]).exists()
    assert "williams_plot" in figs and Path(figs["williams_plot"]["pdf"]).exists()
