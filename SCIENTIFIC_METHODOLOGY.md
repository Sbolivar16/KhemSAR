# Scientific Methodology — KhemSAR

KhemSAR implements reproducible cheminformatics and QSAR/SAR workflows aligned with the **5 OECD Principles for QSAR Validation** and best practices described by Fourches et al., Tropsha, Gramatica, and Todeschini.

## 1. Chemical & Biological Curation
- **Standardization (`khemsar/chemistry/curation.py`):** Counterion/salt stripping (`LargestFragmentChooser`), charge neutralization (`Uncharger`), canonical tautomer selection (`TautomerEnumerator`), exclusion of inorganic/organometallic species and multicomponent organic mixtures, and `InChIKey` generation.
- **Assay & Unit Hygiene:** Strict separation of bioactivity endpoints (`IC50`, `Ki`, `Kd`, `EC50`). Conversion to molar negative logarithm ($p\text{Act} = -\log_{10}(\text{Activity [M]})$). Censored values (`<`, `>`) are excluded from regression and mapped rigorously only in binary classification when unambiguous relative to the activity cutoff.
- **Replicate Aggregation:** Duplicates sharing `InChIKey` are aggregated by median when $\Delta p\text{Act} \le 0.5$ log units; discordant replicates above threshold are excluded and logged in the PRISMA-like attrition report.

## 2. Descriptors, Splitting & OECD QSAR Validation
- **Representations (`khemsar/chemistry/descriptors.py`):** 14 interpretable 2D physicochemical & medicinal-chemistry descriptors (including QED and Ertl Synthetic Accessibility Score) combined with Morgan ECFP4/ECFP6, MACCS, or Topological fingerprints, plus PAINS and Brenk structural alert screening.
- **Data Splitting (`khemsar/qsar/splitting.py`):** Bemis-Murcko Scaffold Split, Kennard-Stone diversity split, Temporal split (by publication year), and Stratified split.
- **Modeling (`khemsar/qsar/modeling.py`):** Leak-free `Pipeline(VarianceThreshold, StandardScaler, Estimator)` with inner cross-validation hyperparameter tuning across PLS, Ridge, ElasticNet, Random Forest, Extra Trees, HistGradientBoosting, SVR/SVC, MLP, XGBoost, and LightGBM.
- **Validation (`khemsar/qsar/validation.py`):**
  - Regression: $R^2_{\text{train}}, Q^2_{\text{CV}}, R^2_{\text{ext}}, Q^2_{F1}, Q^2_{F2}, Q^2_{F3}$, Lin's CCC, RMSE, MAE, and **Golbraikh–Tropsha** criteria ($k, k', R_0^2, R_0'^2$).
  - Classification: MCC, ROC-AUC, PR-AUC, Balanced Accuracy, Sensitivity, Specificity, F1, Cohen's $\kappa$.
  - **Y-Scrambling:** Repeated target permutation with Todeschini $cR_p^2$.
  - **Applicability Domain (AD):** Leverage **Williams Plot** ($h^* = 3p/n_{\text{train}}$, $\pm 3\sigma$ standardized residuals) coupled with 3-NN Tanimoto similarity AD.

## 3. SAR, Interpretability & De Novo Design
- **SAR (`khemsar/sar/`):** SALI Activity Cliffs, Hussain–Rea Matched Molecular Pairs (`rdMMPA`), R-Group decomposition, global SHAP feature attribution, and per-atom 2D attribution SVG maps.
- **Bioisosteric De Novo & 3D Prep (`khemsar/denovo/`):** Curated medicinal-chemistry SMIRKS bioisosteres + dataset-learned MMP transforms + BRICS fragment recombination ranked by Multi-Parameter Optimization (MPO). Exported ligands undergo heuristic physiological pH 7.4 protonation, **ETKDGv3** 3D conformer generation, and **MMFF94s/UFF** energy minimization alongside cleaned RCSB PDB receptors and docking grid box coordinates.
