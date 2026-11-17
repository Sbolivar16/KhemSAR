"""Dataset splitting strategies: Stratified, Bemis-Murcko Scaffold, Kennard-Stone, and Temporal."""

from __future__ import annotations

from typing import Any

import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import StandardScaler


def _scaffold_smiles(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return smiles
    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        return scaf or smiles
    except Exception:
        return smiles


def split_dataset(
    smiles_list: list[str],
    y: np.ndarray,
    X: np.ndarray | None = None,
    years: list[Any] | None = None,
    method: str = "scaffold",  # scaffold | kennard_stone | temporal | stratified
    test_size: float = 0.2,
    task_type: str = "regression",
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray, str]:
    """Return (train_indices, test_indices, actual_method_used)."""
    n = len(smiles_list)
    if n < 10:
        raise ValueError("At least 10 curated molecules are required to split train/test sets.")
    n_test = max(2, int(round(n * test_size)))
    n_train = n - n_test

    m = method.lower()
    if m == "temporal" and years is not None:
        parsed_years = [int(yr) if (yr is not None and str(yr).strip().isdigit()) else None for yr in years]
        valid_count = sum(1 for yr in parsed_years if yr is not None)
        if valid_count >= int(0.7 * n):
            order = sorted(
                range(n),
                key=lambda i: (parsed_years[i] is None, parsed_years[i] if parsed_years[i] is not None else 9999, i),
            )
            return np.asarray(order[:n_train], dtype=int), np.asarray(order[n_train:], dtype=int), "temporal"
        m = "scaffold"

    if m == "scaffold":
        scaf_groups: dict[str, list[int]] = {}
        for idx, smi in enumerate(smiles_list):
            scaf_groups.setdefault(_scaffold_smiles(smi), []).append(idx)
        # Sort scaffolds by group size descending, with deterministic tie-breaker
        rng = np.random.default_rng(random_state)
        grouped = list(scaf_groups.values())
        rng.shuffle(grouped)
        grouped.sort(key=len, reverse=True)
        train_idx: list[int] = []
        test_idx: list[int] = []
        for grp in grouped:
            if len(train_idx) + len(grp) <= n_train or len(test_idx) >= n_test:
                train_idx.extend(grp)
            else:
                test_idx.extend(grp)
        if len(test_idx) >= 2 and len(train_idx) >= 5:
            return np.asarray(sorted(train_idx), dtype=int), np.asarray(sorted(test_idx), dtype=int), "scaffold"
        m = "stratified"

    if m == "kennard_stone" and X is not None and len(X) == n:
        Xs = StandardScaler().fit_transform(np.nan_to_num(X, nan=0.0))
        # Compute pairwise squared Euclidean distance matrix
        sq_norms = np.sum(Xs**2, axis=1, keepdims=True)
        dist2 = np.maximum(0.0, sq_norms + sq_norms.T - 2.0 * (Xs @ Xs.T))
        # Seed with the two most distant molecules
        i0, i1 = np.unravel_index(np.argmax(dist2), dist2.shape)
        selected = [int(i0), int(i1)]
        remaining = set(range(n)) - set(selected)
        min_d = np.minimum(dist2[:, i0], dist2[:, i1])
        while len(selected) < n_train and remaining:
            rem_list = list(remaining)
            best_local = int(np.argmax(min_d[rem_list]))
            nxt = rem_list[best_local]
            selected.append(nxt)
            remaining.remove(nxt)
            min_d = np.minimum(min_d, dist2[:, nxt])
        train_idx_ks = np.asarray(sorted(selected), dtype=int)
        test_idx_ks = np.asarray(sorted(remaining), dtype=int)
        return train_idx_ks, test_idx_ks, "kennard_stone"

    # Stratified split (quantile bins for regression)
    if task_type == "classification":
        strata = y.astype(int)
    else:
        n_bins = min(5, max(2, n // 8))
        quantiles = np.linspace(0, 1, n_bins + 1)
        edges = np.unique(np.quantile(y, quantiles))
        strata = np.digitize(y, edges[1:-1], right=True) if len(edges) > 2 else np.zeros(n, dtype=int)

    try:
        sss = StratifiedShuffleSplit(n_splits=1, test_size=n_test, random_state=random_state)
        tr, te = next(sss.split(np.zeros(n), strata))
        return np.asarray(tr, dtype=int), np.asarray(te, dtype=int), "stratified"
    except Exception:
        rng = np.random.default_rng(random_state)
        perm = rng.permutation(n)
        return perm[:n_train], perm[n_train:], "random"
