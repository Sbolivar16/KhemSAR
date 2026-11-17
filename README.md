# KhemSAR

**Rigorous AI-Assisted QSAR/SAR Modeling, Scientific Tutoring, and Bioisosteric *De Novo* Molecule Design Platform**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10–3.12](https://img.shields.io/badge/Python-3.10%E2%80%933.12-3776AB.svg)](https://www.python.org/)
[![OECD QSAR Principles](https://img.shields.io/badge/OECD-5%20Principles%20Compliant-009E73.svg)](SCIENTIFIC_METHODOLOGY.md)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24308700.svg)](https://doi.org/10.5281/zenodo.24308700)

**Authors:** Santiago Bolívar Ávila ([ORCID 0000-0002-3772-7604](https://orcid.org/0000-0002-3772-7604)), Richard Navarro, Pierine España Puccini  
**Affiliations:** Master's Programme in Biotechnology, Universidad Libre, Puerto Colombia, Colombia; Departamento de Química, Facultad de Ciencias Básicas, Universidad del Atlántico, Puerto Colombia, Colombia; IMB-Research Group in Medicine and Biotechnology, Universidad Libre, Puerto Colombia, Colombia  
**Repository:** [https://github.com/Sbolivar16/KhemSAR](https://github.com/Sbolivar16/KhemSAR)

---

## Overview (EN / ES / PT)

**KhemSAR** is a cross-platform (**macOS, Linux, Windows**) and trilingual (**Español, English, Português**) computational medicinal chemistry platform built to produce **paper-ready QSAR and SAR studies** alongside an interactive **AI Scientific Tutor**.

### Two Integrated Pillars

1. **AI Scientific Tutor ("Understand & Interpret")**
   - Five structured lessons explaining **what SAR and QSAR do, why they are used, and how to interpret results scientifically**.
   - Interactive self-assessment quizzes and a **Contextual Study Interpreter** that reads your active study metrics ($Q^2_{\text{CV}}$, $R^2_{\text{ext}}$, Golbraikh–Tropsha, $cR_p^2$, Williams Plot outliers, SALI cliffs, SHAP features, and *de novo* candidates).
   - Supports **Ollama (100 % local private LLMs)**, **Google Gemini (Gmail / AI Studio)**, **OpenAI**, **Anthropic**, plus a **deterministic offline scientific engine** (works with zero API keys).

2. **Paper-Ready QSAR / SAR & *De Novo* Studio**
   - **Natural-Language AI Copilot + 10 Open Scientific Connectors**: ChEMBL, PubChem, BindingDB, RCSB PDB, UniProt, AlphaFold DB, IUPHAR/BPS Guide to PHARMACOLOGY (`GtoPdb`), Open Targets Platform, COCONUT Natural Products, and EMBL-EBI UniChem.
   - **3D Receptor Preparation & 3Dmol.js Viewer**: Fetches PDB structures, separates clean receptor chains from waters/ions and co-crystallized ligands, and calculates the docking grid box.
   - **Fourches et al. Chemical Curation**: Salt stripping, neutralization, tautomer canonicalization, organic/mixture filtering, strict endpoint separation (`IC50`, `Ki`, `Kd`, `EC50`), censored-value handling, and `InChIKey` duplicate aggregation with PRISMA-style attrition tracking.
   - **OECD-Compliant QSAR Modeling**: Hybrid 2D descriptors + ECFP4/MACCS fingerprints; **Bemis-Murcko Scaffold**, **Kennard-Stone**, **Temporal**, and **Stratified** splits; nested CV across PLS, Ridge, ElasticNet, Random Forest, Extra Trees, HistGradientBoosting, SVR/SVC, MLP, XGBoost, and LightGBM; Golbraikh–Tropsha criteria, $Q^2_{F1/F2/F3}$, CCC, MCC, **Y-scrambling** ($cR_p^2$), and **Williams Plot + k-NN Tanimoto Applicability Domain**.
   - **SAR & Mechanistic Interpretability**: Activity Cliffs (**SALI**), 2D chemical space (PCA / t-SNE / UMAP), **Matched Molecular Pairs (MMP)**, **R-Group decomposition**, **SHAP** global importance, and **2D atomic attribution SVG maps**.
   - **Publication Figures**: Export **SVG, PDF, and 300/600 DPI PNG** figures with colorblind-safe Okabe-Ito palettes and optional English labels for international manuscripts.
   - **Bioisosteric *De Novo* Design & 3D Docking/MD Export**: Curated medicinal-chemistry bioisosteric replacements + dataset-learned MMP transforms + BRICS recombination scored by Multi-Parameter Optimization (QSAR potency + AD + QED + SA Score + PAINS/Brenk). Exports **pH 7.4 protonated**, **ETKDGv3 3D**, **MMFF94/UFF minimized** `.sdf`, `.pdb`, `.csv`, `.xlsx`, clean receptor `.pdb`, and AutoDock Vina grid configuration.
   - **Cloud & Backup**: Sync portable `.qsarproj.zip` bundles with **TeraBox (1 TB free)**, **Google Drive (Gmail)**, or **Dropbox**, plus folder-link quick backup and **Google Colab** `.ipynb` export.

---

## Screenshots

### 1. AI Science Tutor & Contextual Study Interpretation
![AI Science Tutor](docs/screenshots/01_ai_tutor_en.png)

### 2. 3D PDB Receptor Viewer (`3LN1`) & Fourches Chemical Curation (2D Gallery)
![3D PDB & Curation](docs/screenshots/02_curation_pdb3d_en.png)
![Curated 2D Structures](docs/screenshots/02b_curated_structures_2d_en.png)

### 3. OECD QSAR Validation (Linear Regression, Williams Plot, Y-Scrambling & 2D Table)
![QSAR Linear Regression & Validation](docs/screenshots/03_qsar_regression_validation_en.png)
![Train & Test 2D Molecules](docs/screenshots/03b_qsar_molecules_2d_en.png)

### 4. SAR Chemical Space & 2D Atomic Attribution Map
![SAR & Atomic Attribution](docs/screenshots/04_sar_atomic_map_en.png)

### 5. Bioisosteric *De Novo* Design (Multi-Objective MPO)
![De Novo Bioisosteres](docs/screenshots/05_denovo_bioisosteres_en.png)

### 6. Cloud Storage & Google Colab Backup
![Cloud & Backup](docs/screenshots/06_cloud_backup_en.png)

---

## Quick Start

```bash
git clone https://github.com/Sbolivar16/KhemSAR.git
cd KhemSAR
```

- **macOS / Linux:** `./install_and_run.sh`
- **Windows:** `install_and_run.bat`

Then open `http://127.0.0.1:8765` in your browser. See [INSTALL.md](INSTALL.md) for detailed instructions.

---

## How to Cite

Please cite the version of **KhemSAR** you used. For v1.0.1 (which contains the corrected cRp2 calculation, see [CHANGELOG.md](CHANGELOG.md)) use the version DOI [10.5281/zenodo.24318136](https://doi.org/10.5281/zenodo.24318136). The concept DOI [10.5281/zenodo.24308700](https://doi.org/10.5281/zenodo.24308700) always resolves to the latest release. Metadata is also available in `CITATION.cff`.

```bibtex
@software{bolivar_avila_khemsar_2026,
  author       = {Bol{\'i}var {\'A}vila, Santiago and Navarro, Richard and Espa{\~n}a Puccini, Pierine},
  title        = {{KhemSAR: An Open-Source Platform for OECD-Aligned QSAR Validation, Mechanistic SAR Interpretation and Bioisosteric De Novo Design}},
  year         = {2026},
  publisher    = {Zenodo},
  version      = {v1.0.1},
  doi          = {10.5281/zenodo.24318136},
  url          = {https://doi.org/10.5281/zenodo.24318136},
  note         = {Source code: https://github.com/Sbolivar16/KhemSAR}
}
```

