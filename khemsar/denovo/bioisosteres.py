"""Curated medicinal-chemistry bioisosteric transformation library + MMP-derived replacements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem


@dataclass(frozen=True)
class BioisostereRule:
    rule_id: str
    category: str
    description: str
    smirks: str


BIOISOSTERE_RULES: list[BioisostereRule] = [
    BioisostereRule(
        "COOH_to_Tetrazole",
        "Carboxylic Acid Isostere",
        "Carboxylic acid -> 1H-tetrazole (pKa ~4.9, improved permeability & metabolic stability)",
        "[C:1](=[O:2])[OH]>>[c:1]1[nH]nnn1",
    ),
    BioisostereRule(
        "COOH_to_Acylsulfonamide",
        "Carboxylic Acid Isostere",
        "Carboxylic acid -> methyl acylsulfonamide (acidic NH mimic with tunable pKa)",
        "[C:1](=[O:2])[OH]>>[C:1](=[O:2])NS(=O)(=O)C",
    ),
    BioisostereRule(
        "COOH_to_Oxadiazolone",
        "Carboxylic Acid Isostere",
        "Carboxylic acid -> 1,2,4-oxadiazol-5(4H)-one (non-classical planar acid bioisostere)",
        "[C:1](=[O:2])[OH]>>[c:1]1noc(=O)[nH]1",
    ),
    BioisostereRule(
        "SO2NH2_to_SO2Me",
        "Sulfonamide Isostere",
        "Primary arylsulfonamide -> methyl sulfone (modulates selectivity & HBD count)",
        "[c:1]S(=O)(=O)[NH2]>>[c:1]S(=O)(=O)C",
    ),
    BioisostereRule(
        "SO2Me_to_SO2NH2",
        "Sulfone Isostere",
        "Methyl sulfone -> primary sulfonamide (adds H-bond donor capacity)",
        "[c:1]S(=O)(=O)[CH3]>>[c:1]S(=O)(=O)N",
    ),
    BioisostereRule(
        "Amide_to_123Triazole",
        "Amide Isostere",
        "Secondary amide -> 1,4-disubstituted 1,2,3-triazole (protease-resistant H-bond mimic)",
        "[*:1][C:2](=[O:3])[NH:4][*:5]>>[*:1][c:2]1cn([*:5])nn1",
    ),
    BioisostereRule(
        "Amide_to_Oxadiazole",
        "Amide Isostere",
        "Secondary amide -> 1,3,4-oxadiazole (rigidified planar amide bioisostere)",
        "[*:1][C:2](=[O:3])[NH:4][*:5]>>[*:1][c:2]1nnc([*:5])o1",
    ),
    BioisostereRule(
        "Ester_to_Oxadiazole",
        "Ester Isostere",
        "Ester -> 1,2,4-oxadiazole (hydrolytically stable ester replacement)",
        "[*:1][C:2](=[O:3])[O:4][*:5]>>[*:1][c:2]1noc([*:5])n1",
    ),
    BioisostereRule(
        "ArylH_to_F",
        "Halogen / Metabolic Block",
        "Para/meta aryl C-H -> C-F (blocks CYP oxidation & tunes electronics)",
        "[cH:1]>>[c:1]F",
    ),
    BioisostereRule(
        "ArylH_to_Cl",
        "Halogen / Hydrophobic Pocket",
        "Aryl C-H -> C-Cl (lipophilic sigma-hole halogen bonding)",
        "[cH:1]>>[c:1]Cl",
    ),
    BioisostereRule(
        "ArylH_to_CF3",
        "Halogen / Electron-Withdrawing",
        "Aryl C-H -> C-CF3 (metabolic stability & hydrophobic fill)",
        "[cH:1]>>[c:1]C(F)(F)F",
    ),
    BioisostereRule(
        "ArylMe_to_CF3",
        "Methyl Isostere",
        "Aryl methyl -> trifluoromethyl (blocks benzylic oxidation)",
        "[c:1][CH3]>>[c:1]C(F)(F)F",
    ),
    BioisostereRule(
        "ArylCF3_to_OCF3",
        "Trifluoromethyl Isostere",
        "Aryl CF3 -> OCF3 (adjusts dipole & orthogonal conformation)",
        "[c:1]C(F)(F)F>>[c:1]OC(F)(F)F",
    ),
    BioisostereRule(
        "ArylOMe_to_OCF3",
        "Alkoxy Isostere",
        "Aryl methoxy -> trifluoromethoxy (blocks O-demethylation)",
        "[c:1]O[CH3]>>[c:1]OC(F)(F)F",
    ),
    BioisostereRule(
        "ArylCl_to_CN",
        "Halogen / Polar Isostere",
        "Aryl chloride -> nitrile (reduces logP while keeping dipole)",
        "[c:1]Cl>>[c:1]C#N",
    ),
    BioisostereRule(
        "Phenyl_to_Pyridine",
        "Ring Bioisostere",
        "Monosubstituted phenyl -> 4-pyridyl (lowers logP, adds HBA)",
        "[*:1]-[c]1[cH][cH][cH][cH][cH]1>>[*:1]-c1ccncc1",
    ),
    BioisostereRule(
        "Phenyl_to_Thiophene",
        "Ring Bioisostere",
        "Monosubstituted phenyl -> 2-thienyl (classical benzene-thiophene isostere)",
        "[*:1]-[c]1[cH][cH][cH][cH][cH]1>>[*:1]-c1cccs1",
    ),
    BioisostereRule(
        "Phenyl_to_BCP",
        "3D sp3 Phenyl Isostere",
        "Monosubstituted phenyl -> bicyclo[1.1.1]pentane (increases Fsp3 & solubility)",
        "[*:1]-[c]1[cH][cH][cH][cH][cH]1>>[*:1]-C12CC(C1)C2",
    ),
    BioisostereRule(
        "ArylOH_to_NHSO2Me",
        "Phenol Isostere",
        "Phenol -> methanesulfonamide (avoids glucuronidation while keeping HBD)",
        "[c:1][OH]>>[c:1]NS(=O)(=O)C",
    ),
]


def apply_bioisosteric_replacements(
    smiles: str,
    max_variants: int = 30,
    mmp_transforms: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Apply curated SMIRKS bioisostere rules (and optional dataset MMP transforms) to a parent SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []

    parent_can = Chem.MolToSmiles(mol, isomericSmiles=False, canonical=True)
    seen: set[str] = {parent_can}
    variants: list[dict[str, str]] = []

    for rule in BIOISOSTERE_RULES:
        try:
            rxn = AllChem.ReactionFromSmarts(rule.smirks)
            products = rxn.RunReactants((mol,))
        except Exception:
            continue
        added_for_rule = 0
        for prod_tuple in products:
            if not prod_tuple:
                continue
            prod = prod_tuple[0]
            try:
                Chem.SanitizeMol(prod)
                can = Chem.MolToSmiles(prod, isomericSmiles=False, canonical=True)
            except Exception:
                continue
            if can in seen or prod.GetNumHeavyAtoms() > 65:
                continue
            seen.add(can)
            variants.append(
                {
                    "smiles": can,
                    "rule_id": rule.rule_id,
                    "category": rule.category,
                    "description": rule.description,
                }
            )
            added_for_rule += 1
            if added_for_rule >= 2 or len(variants) >= max_variants:
                break
        if len(variants) >= max_variants:
            break

    # Apply top dataset-specific MMP replacements when provided
    if mmp_transforms and len(variants) < max_variants:
        for tr in mmp_transforms[:10]:
            lhs = tr.get("from_fragment", "")
            rhs = tr.get("to_fragment", "")
            if not lhs or not rhs or "[*:1]" not in lhs:
                continue
            try:
                # Convert dummy attachment [*:1] / [1*] to valid reaction SMIRKS if single-cut
                lhs_clean = lhs.replace("[1*]", "[*:1]")
                rhs_clean = rhs.replace("[1*]", "[*:1]")
                if "[*:1]" not in lhs_clean or "[*:1]" not in rhs_clean:
                    continue
                rxn = AllChem.ReactionFromSmarts(f"{lhs_clean}>>{rhs_clean}")
                products = rxn.RunReactants((mol,))
                for prod_tuple in products:
                    prod = prod_tuple[0]
                    Chem.SanitizeMol(prod)
                    can = Chem.MolToSmiles(prod, isomericSmiles=False, canonical=True)
                    if can not in seen:
                        seen.add(can)
                        variants.append(
                            {
                                "smiles": can,
                                "rule_id": "Dataset_MMP_Transform",
                                "category": "Data-Driven MMP Bioisostere",
                                "description": f"Learned SAR transform: {lhs} -> {rhs} (mean dP={tr.get('mean_delta_pActivity', 0)})",
                            }
                        )
                        break
            except Exception:
                continue
            if len(variants) >= max_variants:
                break

    return variants
