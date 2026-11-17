# KhemSAR Installation & System Requirements Guide (ES / EN / PT)

## System Requirements / Requisitos del Sistema / Requisitos do Sistema

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | macOS 12+, Ubuntu 20.04+ / Linux x86_64/arm64, Windows 10/11 | macOS 14+, Ubuntu 22.04+, Windows 11 |
| **Python** | 3.10 | **3.11** (supported: 3.10–3.12) |
| **RAM** | 4 GB | 8–16 GB (for large ChEMBL sets & 3D conformers) |
| **Disk** | 1.5 GB | 3 GB+ (plus TeraBox/Google Drive/Dropbox for study backups) |
| **Internet** | Optional (offline demo & Tutor work offline) | Required for ChEMBL, PubChem, PDB, BindingDB, Cloud LLMs |

---

## Option 1: One-Click Install & Run (Recommended)

### macOS & Linux
```bash
git clone https://github.com/Sbolivar16/KhemSAR.git
cd KhemSAR
./install_and_run.sh
```

### Windows (Command Prompt or PowerShell)
```bat
git clone https://github.com/Sbolivar16/KhemSAR.git
cd KhemSAR
install_and_run.bat
```

---

## Option 2: Conda / Miniforge (Most Stable for RDKit & XGBoost/LightGBM)

```bash
conda env create -f environment.yml
conda activate khemsar
khemsar
```

---

## Option 3: `uv` + Python Virtual Environment

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install -e ".[ml,dev]"
python -m khemsar.main
```

*Optional extras:*
- `pip install -e ".[umap]"` for UMAP 2D chemical space projections.
- `pip install -e ".[docking]"` for `meeko` PDBQT preparation.

---

## Local AI (Ollama) & Cloud Storage Setup

1. **Private Local LLM (Ollama):** Install [Ollama](https://ollama.com), run `ollama pull llama3.1`, and select **Ollama** inside KhemSAR's *Settings & AI* tab.
2. **Gmail / Google Gemini:** Create a free API key in Google AI Studio using your Gmail account and paste it into KhemSAR *Settings & AI* (stored only locally on your machine).
3. **Cloud Storage (Google Drive / Gmail, TeraBox 1 TB, Dropbox):**
   - **Easiest (Folder Link):** Paste your Google Drive, TeraBox (1 TB free), or Dropbox folder link inside the **Cloud & Backup** tab; KhemSAR packages `.qsarproj.zip`, reveals it locally, and opens your cloud folder for quick drag-and-drop.
   - **Auto Desktop Sync:** Install **TeraBox Desktop**, **Google Drive for Desktop**, or **Dropbox** so KhemSAR auto-detects and syncs directly to your local cloud folder.
   - **Google Colab (with Gmail):** Export a ready-to-run `.ipynb` notebook that mounts your Google Drive directly with standard Gmail login.
   - *(Optional Advanced)*: Configure your own OAuth 2.0 Client ID inside the collapsible *Advanced OAuth* section if needed.
