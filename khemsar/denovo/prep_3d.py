"""3D conformer generation (pH 7.4 heuristic protonation, ETKDGv3, MMFF94/UFF) for Docking & MD."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem

# Physiological pH 7.4 heuristic protonation transforms (documented approximation)
_PH74_RULES = [
    # Carboxylic acid -> carboxylate
    ("[CX3:1](=[OX1:2])[OX2H1]", "[C:1](=[O:2])[O-]"),
    # Acylsulfonamide -> deprotonated acylsulfonamide
    ("[CX3:1](=[OX1:2])[NH1:3][SX4:4](=[O:5])(=[O:6])", "[C:1](=[O:2])[N-:3][S:4](=[O:5])(=[O:6])"),
    # 1H-Tetrazole -> tetrazolate
    ("c1[nH]nnn1", "c1[n-]nnn1"),
    # Primary/secondary/tertiary aliphatic amines (non-amide, non-aniline, non-sulfonamide) -> protonated
    ("[NX3;H2,H1,H0;!$(NC=O);!$(NS=O);!$(Nc);!$([N+])][CX4:1]", "[N+:0][C:1]"),
]


def approximate_ph74_state(mol: Chem.Mol) -> Chem.Mol:
    """Apply heuristic physiological pH 7.4 protonation state for docking/MD readiness."""
    cur = Chem.Mol(mol)
    for smarts_from, smarts_to in _PH74_RULES[:3]:
        try:
            rxn = AllChem.ReactionFromSmarts(f"{smarts_from}>>{smarts_to}")
            prods = rxn.RunReactants((cur,))
            if prods and prods[0]:
                cand = prods[0][0]
                Chem.SanitizeMol(cand)
                cur = cand
        except Exception:
            continue

    # Protonate aliphatic basic nitrogens cleanly on atom level
    rw = Chem.RWMol(cur)
    basic_pat = Chem.MolFromSmarts("[NX3;H2,H1,H0;!$(NC=O);!$(NS=O);!$(Nc);!$(N=*);!$(N#*)]")
    if basic_pat is not None:
        matches = rw.GetSubstructMatches(basic_pat)
        for (idx,) in matches:
            atom = rw.GetAtomWithIdx(idx)
            if atom.GetFormalCharge() == 0:
                atom.SetFormalCharge(1)
                atom.SetNumExplicitHs(atom.GetTotalNumHs() + 1)
    try:
        m_out = rw.GetMol()
        Chem.SanitizeMol(m_out)
        return m_out
    except Exception:
        return cur


def generate_3d_conformer(
    smiles: str,
    protonate_ph74: bool = True,
    force_field: str = "MMFF94",
    seed: int = 42,
) -> tuple[Chem.Mol | None, dict[str, Any]]:
    """Embed a 3D conformer using ETKDGv3 and minimize energy with MMFF94 or UFF."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, {"ok": False, "error": "Invalid SMILES"}

    if protonate_ph74:
        mol = approximate_ph74_state(mol)

    mol_h = Chem.AddHs(mol, addCoords=False)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    params.useSmallRingTorsions = True
    status = AllChem.EmbedMolecule(mol_h, params)
    if status != 0:
        # Fallback random coords if ETKDG struggles on strained rings
        status = AllChem.EmbedMolecule(mol_h, AllChem.ETKDGv3())
    if status != 0:
        return None, {"ok": False, "error": "3D embedding failed"}

    energy = None
    ff_used = force_field
    if force_field.upper().startswith("MMFF") and AllChem.MMFFHasAllMoleculeParams(mol_h):
        props = AllChem.MMFFGetMoleculeProperties(mol_h, mmffVariant="MMFF94s")
        ff = AllChem.MMFFGetMoleculeForceField(mol_h, props)
        if ff is not None:
            ff.Minimize(maxIts=500)
            energy = round(float(ff.CalcEnergy()), 3)
            ff_used = "MMFF94s"
    if energy is None:
        ff = AllChem.UFFGetMoleculeForceField(mol_h)
        if ff is not None:
            ff.Minimize(maxIts=500)
            energy = round(float(ff.CalcEnergy()), 3)
            ff_used = "UFF"

    return mol_h, {
        "ok": True,
        "force_field": ff_used,
        "energy_kcal_mol": energy,
        "formal_charge_ph74": int(Chem.GetFormalCharge(mol_h)),
    }


def export_docking_md_library(
    candidates: list[dict[str, Any]],
    output_dir: Path | str,
    protonate_ph74: bool = True,
    force_field: str = "MMFF94",
    receptor_pdb: str = "",
    cocrystal_ligand_pdb: str = "",
    docking_box: dict[str, Any] | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Generate 3D minimized SDF, PDB ligands, CSV/XLSX table, and Vina/GROMACS/AMBER guide."""
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ligands_pdb_dir = out_dir / "ligands_pdb"
    ligands_pdb_dir.mkdir(exist_ok=True)

    sdf_path = out_dir / "khemsar_denovo_3d.sdf"
    csv_path = out_dir / "khemsar_denovo_library.csv"
    xlsx_path = out_dir / "khemsar_denovo_library.xlsx"

    writer = Chem.SDWriter(str(sdf_path))
    rows_summary: list[dict[str, Any]] = []
    n_3d_ok = 0

    total_cands = max(1, len(candidates))
    for idx, cand in enumerate(candidates):
        cid = cand.get("candidate_id") or cand.get("compound_id") or f"LIG_{idx+1:03d}"
        if progress_cb:
            progress_cb(5 + int(87 * ((idx + 1) / total_cands)), f"3D ETKDGv3 + {force_field} ({idx + 1}/{total_cands}): {cid}")
        smi = cand["smiles"]
        mol_3d, meta_3d = generate_3d_conformer(
            smi, protonate_ph74=protonate_ph74, force_field=force_field, seed=42 + idx
        )
        row = dict(cand)
        row["pH74_charge"] = meta_3d.get("formal_charge_ph74")
        row["force_field_3d"] = meta_3d.get("force_field", "")
        row["energy_kcal_mol"] = meta_3d.get("energy_kcal_mol")
        row["conformer_3d_ok"] = bool(meta_3d.get("ok"))

        if mol_3d is not None:
            n_3d_ok += 1
            mol_3d.SetProp("_Name", str(cid))
            for k in (
                "smiles",
                "origin",
                "bioisostere_rule",
                "predicted_pActivity",
                "MPO_score",
                "in_ad",
                "QED",
                "SA_Score",
                "MolWt",
                "MolLogP",
                "TPSA",
            ):
                if k in cand and cand[k] is not None:
                    mol_3d.SetProp(k, str(cand[k]))
            mol_3d.SetProp("pH74_charge", str(row["pH74_charge"]))
            mol_3d.SetProp("force_field_3d", str(row["force_field_3d"]))
            if row["energy_kcal_mol"] is not None:
                mol_3d.SetProp("energy_kcal_mol", str(row["energy_kcal_mol"]))
            writer.write(mol_3d)

            pdb_block = Chem.MolToPDBBlock(mol_3d)
            (ligands_pdb_dir / f"{cid}.pdb").write_text(pdb_block, encoding="utf-8")

        rows_summary.append(row)

    writer.close()

    if progress_cb:
        progress_cb(95, "Writing SDF, PDB, CSV, XLSX and Vina configuration...")
    df = pd.DataFrame(rows_summary)
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    files_created = {
        "sdf_3d": str(sdf_path),
        "csv": str(csv_path),
        "xlsx": str(xlsx_path),
        "ligands_pdb_dir": str(ligands_pdb_dir),
    }

    if receptor_pdb:
        rec_path = out_dir / "receptor_clean.pdb"
        rec_path.write_text(receptor_pdb, encoding="utf-8")
        files_created["receptor_pdb"] = str(rec_path)

    if cocrystal_ligand_pdb:
        lig_ref_path = out_dir / "cocrystal_reference_ligand.pdb"
        lig_ref_path.write_text(cocrystal_ligand_pdb, encoding="utf-8")
        files_created["cocrystal_ligand_pdb"] = str(lig_ref_path)

    box = docking_box or {}
    vina_txt = (
        f"receptor = receptor_clean.pdbqt\n"
        f"center_x = {box.get('center_x', 0.0)}\n"
        f"center_y = {box.get('center_y', 0.0)}\n"
        f"center_z = {box.get('center_z', 0.0)}\n"
        f"size_x = {box.get('size_x', 22.0)}\n"
        f"size_y = {box.get('size_y', 22.0)}\n"
        f"size_z = {box.get('size_z', 22.0)}\n"
        f"exhaustiveness = 16\n"
    )
    vina_cfg_path = out_dir / "vina_config_template.txt"
    vina_cfg_path.write_text(vina_txt, encoding="utf-8")
    files_created["vina_config"] = str(vina_cfg_path)

    return {
        "n_total": len(candidates),
        "n_3d_embedded": n_3d_ok,
        "files": files_created,
        "summary_rows": rows_summary,
    }
