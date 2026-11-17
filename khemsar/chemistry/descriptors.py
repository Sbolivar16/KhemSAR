"""Molecular descriptors, medicinal chemistry filters, SA score, and fingerprints."""

from __future__ import annotations

import os
import sys
from typing import Any

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import QED, Crippen, Descriptors, FilterCatalog, Lipinski, RDConfig, rdFingerprintGenerator, rdMolDescriptors

# Load RDKit's built-in Ertl Synthetic Accessibility scorer cleanly
_SA_SCORER = None
try:
    _sa_dir = os.path.join(RDConfig.RDContribDir, "SA_Score")
    if os.path.isdir(_sa_dir) and _sa_dir not in sys.path:
        sys.path.append(_sa_dir)
    import sascorer as _rdkit_sascorer  # type: ignore

    _SA_SCORER = _rdkit_sascorer
except Exception:
    _SA_SCORER = None

# Initialize PAINS and Brenk structural alert catalogs once
_PAINS_PARAMS = FilterCatalog.FilterCatalogParams()
_PAINS_PARAMS.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
_PAINS_CATALOG = FilterCatalog.FilterCatalog(_PAINS_PARAMS)

_BRENK_PARAMS = FilterCatalog.FilterCatalogParams()
_BRENK_PARAMS.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.BRENK)
_BRENK_CATALOG = FilterCatalog.FilterCatalog(_BRENK_PARAMS)


PHYSCHEM_DESCRIPTOR_NAMES = [
    "MolWt",
    "MolLogP",
    "TPSA",
    "NumHDonors",
    "NumHAcceptors",
    "NumRotatableBonds",
    "RingCount",
    "NumAromaticRings",
    "FractionCSP3",
    "HeavyAtomCount",
    "FormalCharge",
    "MolMR",
    "BertzCT",
    "QED",
]


def compute_sa_score(mol: Chem.Mol) -> float:
    """Compute Synthetic Accessibility score (1 = easy, 10 = very hard)."""
    if _SA_SCORER is not None:
        try:
            return round(float(_SA_SCORER.calculateScore(mol)), 3)
        except Exception:
            pass
    # Clean heuristic fallback if contrib SA_Score data file is absent
    rings = rdMolDescriptors.CalcNumRings(mol)
    spiro = rdMolDescriptors.CalcNumSpiroAtoms(mol)
    bridge = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    chiral = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True))
    heavy = max(1, mol.GetNumHeavyAtoms())
    score = 1.5 + 0.04 * heavy + 0.25 * rings + 0.6 * chiral + 0.8 * (spiro + bridge)
    return round(float(min(10.0, max(1.0, score))), 3)


def evaluate_medchem_profile(mol: Chem.Mol) -> dict[str, Any]:
    """Compute medicinal chemistry properties, Lipinski/Veber compliance, QED, SA, PAINS/Brenk."""
    mw = float(Descriptors.MolWt(mol))
    logp = float(Crippen.MolLogP(mol))
    tpsa = float(rdMolDescriptors.CalcTPSA(mol))
    hbd = int(Lipinski.NumHDonors(mol))
    hba = int(Lipinski.NumHAcceptors(mol))
    rotb = int(Lipinski.NumRotatableBonds(mol))
    rings = int(rdMolDescriptors.CalcNumRings(mol))
    arom_rings = int(rdMolDescriptors.CalcNumAromaticRings(mol))
    fsp3 = float(rdMolDescriptors.CalcFractionCSP3(mol))
    heavy = int(mol.GetNumHeavyAtoms())
    charge = int(Chem.GetFormalCharge(mol))
    mr = float(Crippen.MolMR(mol))
    bertz = float(Descriptors.BertzCT(mol))
    qed_val = float(QED.qed(mol))
    sa_val = compute_sa_score(mol)

    lipinski_violations = int(mw > 500) + int(logp > 5) + int(hbd > 5) + int(hba > 10)
    veber_pass = (rotb <= 10) and (tpsa <= 140)
    pains_matches = [m.GetDescription() for m in _PAINS_CATALOG.GetMatches(mol)]
    brenk_matches = [m.GetDescription() for m in _BRENK_CATALOG.GetMatches(mol)]

    return {
        "MolWt": round(mw, 3),
        "MolLogP": round(logp, 3),
        "TPSA": round(tpsa, 3),
        "NumHDonors": hbd,
        "NumHAcceptors": hba,
        "NumRotatableBonds": rotb,
        "RingCount": rings,
        "NumAromaticRings": arom_rings,
        "FractionCSP3": round(fsp3, 3),
        "HeavyAtomCount": heavy,
        "FormalCharge": charge,
        "MolMR": round(mr, 3),
        "BertzCT": round(bertz, 3),
        "QED": round(qed_val, 3),
        "SA_Score": sa_val,
        "Lipinski_Violations": lipinski_violations,
        "Veber_Pass": bool(veber_pass),
        "PAINS_Alerts": pains_matches,
        "Brenk_Alerts": brenk_matches,
    }


def compute_fingerprint(
    mol: Chem.Mol,
    fp_type: str = "morgan_ecfp4",
    n_bits: int = 1024,
) -> np.ndarray:
    """Compute molecular fingerprint as a uint8 numpy array."""
    kind = fp_type.lower()
    if kind in ("morgan", "morgan_ecfp4", "ecfp4"):
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=n_bits)
        bv = gen.GetFingerprint(mol)
    elif kind in ("morgan_ecfp6", "ecfp6"):
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=3, fpSize=n_bits)
        bv = gen.GetFingerprint(mol)
    elif kind == "maccs":
        from rdkit.Chem import MACCSkeys

        bv = MACCSkeys.GenMACCSKeys(mol)
        arr = np.zeros((bv.GetNumBits(),), dtype=np.uint8)
        DataStructs.ConvertToNumpyArray(bv, arr)
        return arr
    elif kind in ("rdkit", "topological"):
        gen = rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=n_bits)
        bv = gen.GetFingerprint(mol)
    elif kind == "atompair":
        gen = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=n_bits)
        bv = gen.GetFingerprint(mol)
    else:
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=n_bits)
        bv = gen.GetFingerprint(mol)

    arr = np.zeros((n_bits,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(bv, arr)
    return arr


def featurize_smiles_list(
    smiles_list: list[str],
    feature_mode: str = "hybrid",  # physchem | morgan_ecfp4 | maccs | hybrid
    n_bits: int = 512,
) -> tuple[np.ndarray, list[str], list[dict[str, Any]]]:
    """Build feature matrix X, feature names, and per-molecule medicinal chemistry profiles."""
    profiles: list[dict[str, Any]] = []
    physchem_rows: list[list[float]] = []
    fp_rows: list[np.ndarray] = []

    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            raise ValueError(f"Invalid SMILES in featurization: {smi}")
        prof = evaluate_medchem_profile(mol)
        profiles.append(prof)
        physchem_rows.append([float(prof[name]) for name in PHYSCHEM_DESCRIPTOR_NAMES])
        if feature_mode != "physchem":
            fp_type = "maccs" if feature_mode == "maccs" else ("ecfp6" if feature_mode == "ecfp6" else "ecfp4")
            fp_rows.append(compute_fingerprint(mol, fp_type=fp_type, n_bits=n_bits))

    X_phys = np.asarray(physchem_rows, dtype=float)
    if feature_mode == "physchem":
        return X_phys, list(PHYSCHEM_DESCRIPTOR_NAMES), profiles

    X_fp = np.asarray(fp_rows, dtype=float)
    fp_prefix = "MACCS" if feature_mode == "maccs" else "FP"
    fp_names = [f"{fp_prefix}_{i}" for i in range(X_fp.shape[1])]
    if feature_mode in ("morgan_ecfp4", "ecfp4", "ecfp6", "maccs"):
        return X_fp, fp_names, profiles

    # Hybrid: interpretable 2D physicochemical descriptors + fingerprint bits
    X = np.hstack([X_phys, X_fp])
    return X, list(PHYSCHEM_DESCRIPTOR_NAMES) + fp_names, profiles
