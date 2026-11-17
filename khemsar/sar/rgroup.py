"""R-Group Decomposition SAR analysis around an auto-detected or user-specified core."""

from __future__ import annotations

from collections import Counter
from typing import Any

from rdkit import Chem
from rdkit.Chem import rdRGroupDecomposition
from rdkit.Chem.Scaffolds import MurckoScaffold


def decompose_rgroups(
    records: list[dict[str, Any]],
    core_smarts: str | None = None,
    max_rows: int = 50,
) -> dict[str, Any]:
    """Decompose molecules sharing a common core into R1, R2, ... substituent SAR table."""
    mols: list[tuple[dict[str, Any], Chem.Mol]] = []
    for rec in records:
        mol = Chem.MolFromSmiles(rec["smiles"])
        if mol is not None:
            mols.append((rec, mol))

    if len(mols) < 3:
        return {"core_smiles": "", "r_columns": [], "rows": []}

    core_mol = Chem.MolFromSmarts(core_smarts) if core_smarts else None
    used_core_str = core_smarts or ""
    if core_mol is None:
        # Auto-select the most frequent Bemis-Murcko scaffold containing at least 1 ring
        scaffolds: Counter[str] = Counter()
        for _, m in mols:
            try:
                scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False)
                if scaf:
                    scaffolds[scaf] += 1
            except Exception:
                continue
        if not scaffolds:
            return {"core_smiles": "", "r_columns": [], "rows": []}
        used_core_str = scaffolds.most_common(1)[0][0]
        core_mol = Chem.MolFromSmiles(used_core_str)

    if core_mol is None:
        return {"core_smiles": "", "r_columns": [], "rows": []}

    matched_recs: list[dict[str, Any]] = []
    matched_mols: list[Chem.Mol] = []
    for rec, m in mols:
        if m.HasSubstructMatch(core_mol):
            matched_recs.append(rec)
            matched_mols.append(m)

    if len(matched_mols) < 2:
        return {"core_smiles": used_core_str, "r_columns": [], "rows": [], "matched_count": len(matched_mols)}

    try:
        rgd_groups, unmatched = rdRGroupDecomposition.RGroupDecompose(
            [core_mol], matched_mols, asSmiles=True, asRows=True
        )
    except Exception as exc:
        return {"core_smiles": used_core_str, "r_columns": [], "rows": [], "error": str(exc)}

    r_cols: list[str] = []
    rows: list[dict[str, Any]] = []
    # Map matched indices excluding unmatched
    unmatched_set = set(unmatched)
    valid_recs = [r for i, r in enumerate(matched_recs) if i not in unmatched_set]

    for rec, rg in zip(valid_recs, rgd_groups):
        row: dict[str, Any] = {
            "compound_id": rec["compound_id"],
            "name": rec["name"],
            "smiles": rec["smiles"],
            "pActivity": float(rec["pActivity"]),
        }
        for k, v in rg.items():
            if k == "Core":
                continue
            if k not in r_cols:
                r_cols.append(k)
            row[k] = v
        rows.append(row)

    rows.sort(key=lambda x: x["pActivity"], reverse=True)
    return {
        "core_smiles": used_core_str,
        "matched_count": len(rows),
        "r_columns": sorted(r_cols),
        "rows": rows[:max_rows],
    }
