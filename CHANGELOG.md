# Changelog

All notable changes to KhemSAR are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-17

### Fixed
- **cRp2 (Y-scrambling) calculation now follows Rücker et al. (2007).**
  `run_y_scrambling` in `khemsar/qsar/validation.py` computes
  cRp2 = R · sqrt(R² − mean(R²_perm)), using the R² of the model fitted on the
  real responses and the mean R² of the permuted models, with the permuted term
  truncated at zero when it is negative. The formula is isolated in the new
  function `compute_crp2`.
  Two defects in v1.0.0 are corrected:
  1. The cross-validation splitter `cv` was used in `cross_val_predict` before
     it was defined. The resulting error triggered the fallback path, so the
     reported `original_Q2_CV` silently took the value of R²_train.
  2. The cRp2 formula used Q² (cross-validated) in place of R², i.e.
     sqrt(Q²_CV) · sqrt(Q²_CV − mean(Q²_perm)), instead of the R²-based
     expression defined by Rücker et al. (2007).
  cRp2 values produced by v1.0.0 should not be reused; re-run the validation
  with v1.0.1.

### Added
- Unit test `test_crp2_formula_and_y_scrambling_known_values` in
  `tests/test_qsar_and_validation.py`: checks the analytical value of
  `compute_crp2` (R² = 0.81, mean R²_perm = 0.17 → cRp2 = 0.72), the truncation
  to zero, and that `run_y_scrambling` reports a Q²_CV distinct from R²_train
  and a cRp2 consistent with the formula.
- `run_y_scrambling` now also returns the `random_state` used.

### Changed
- Version bumped to 1.0.1; citation metadata (`CITATION.cff`, `.zenodo.json`)
  updated with all three authors, ORCID and revised affiliations.

### Reference
- Rücker, C., Rücker, G., & Meringer, M. (2007). y-Randomization and its
  variants in QSPR/QSAR. *Journal of Chemical Information and Modeling*, 47(6),
  2345–2357. https://doi.org/10.1021/ci700157b

## [1.0.0] - 2026-11-16

- Initial public release.
