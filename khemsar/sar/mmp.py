"""Matched Molecular Pairs (MMP) analysis using RDKit rdMMPA Hussain-Rea fragmentation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdMMPA


def analyze_matched_molecular_pairs(
    records: list[dict[str, Any]],
    max_cuts: int = 1,
    min_pairs: int = 1,
    top_k: int = 30,
) -> dict[str, Any]:
    """Identify Matched Molecular Pairs and rank structural transforms by delta pActivity."""
    if len(records) < 4:
        return {"transforms": [], "pairs": []}

    # Map core_smiles -> list of (record_idx, substituent_smiles)
    core_map: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for idx, rec in enumerate(records):
        mol = Chem.MolFromSmiles(rec["smiles"])
        if mol is None:
            continue
        try:
            frags = rdMMPA.FragmentMol(mol, maxCuts=max_cuts, resultsAsMols=False)
        except Exception:
            continue
        seen_for_mol: set[tuple[str, str]] = set()
        for core, sidechain in frags:
            pairs_to_index: list[tuple[str, str]] = []
            if core and sidechain:
                pairs_to_index.append((core, sidechain))
            elif not core and "." in sidechain:
                parts = sidechain.split(".")
                if len(parts) == 2:
                    a, b = parts
                    # Treat the larger fragment as conserved core and smaller as variable substituent
                    if len(a) >= len(b):
                        pairs_to_index.append((a, b))
                    else:
                        pairs_to_index.append((b, a))
            for c_smi, s_smi in pairs_to_index:
                if len(s_smi) > len(c_smi) * 1.25:
                    continue
                key = (c_smi, s_smi)
                if key in seen_for_mol:
                    continue
                seen_for_mol.add(key)
                core_map[c_smi].append((idx, s_smi))

    transforms_agg: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_mol_pairs: set[tuple[int, int, str]] = set()

    for core, items in core_map.items():
        if len(items) < 2:
            continue
        for i in range(len(items)):
            idx1, frag1 = items[i]
            for j in range(i + 1, len(items)):
                idx2, frag2 = items[j]
                if idx1 == idx2 or frag1 == frag2:
                    continue
                p1 = float(records[idx1]["pActivity"])
                p2 = float(records[idx2]["pActivity"])
                # Orient transform in direction of higher activity when comparing, or canonicalize
                if p2 >= p1:
                    lhs, rhs = frag1, frag2
                    delta = p2 - p1
                    a_rec, b_rec = records[idx1], records[idx2]
                else:
                    lhs, rhs = frag2, frag1
                    delta = p1 - p2
                    a_rec, b_rec = records[idx2], records[idx1]

                smirks = f"{lhs} >> {rhs}"
                pair_key = (min(idx1, idx2), max(idx1, idx2), smirks)
                if pair_key in seen_mol_pairs:
                    continue
                seen_mol_pairs.add(pair_key)
                transforms_agg[smirks].append(
                    {
                        "core": core,
                        "from_id": a_rec["compound_id"],
                        "from_name": a_rec["name"],
                        "from_pActivity": round(float(a_rec["pActivity"]), 3),
                        "to_id": b_rec["compound_id"],
                        "to_name": b_rec["name"],
                        "to_pActivity": round(float(b_rec["pActivity"]), 3),
                        "delta_pActivity": round(float(delta), 3),
                    }
                )

    summary_transforms: list[dict[str, Any]] = []
    all_pairs: list[dict[str, Any]] = []
    for smirks, plist in transforms_agg.items():
        if len(plist) < min_pairs:
            continue
        deltas = [p["delta_pActivity"] for p in plist]
        lhs, rhs = smirks.split(" >> ", 1)
        summary_transforms.append(
            {
                "transform": smirks,
                "from_fragment": lhs,
                "to_fragment": rhs,
                "n_pairs": len(plist),
                "mean_delta_pActivity": round(float(np.mean(deltas)), 3),
                "median_delta_pActivity": round(float(np.median(deltas)), 3),
                "max_delta_pActivity": round(float(np.max(deltas)), 3),
                "example_pair": plist[0],
            }
        )
        for p in plist:
            all_pairs.append({"transform": smirks, **p})

    summary_transforms.sort(key=lambda x: (x["n_pairs"], x["mean_delta_pActivity"]), reverse=True)
    all_pairs.sort(key=lambda x: x["delta_pActivity"], reverse=True)

    return {
        "n_unique_transforms": len(summary_transforms),
        "n_pairs": len(all_pairs),
        "transforms": summary_transforms[:top_k],
        "pairs": all_pairs[:top_k],
    }
