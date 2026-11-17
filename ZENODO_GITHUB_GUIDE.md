# How to Publish KhemSAR on GitHub and Mint a Zenodo DOI

Follow these steps once you are ready to publish `https://github.com/Sbolivar16/KhemSAR` and obtain your permanent citable **DOI**:

## Step 1: Create the GitHub Repository
1. Sign in to GitHub as **Sbolivar16**.
2. Create a new public repository named **`KhemSAR`** (do **not** initialize with README/LICENSE, as KhemSAR already includes them).
3. Push from your terminal inside `KhemSAR/`:
   ```bash
   git add .
   git status   # Verify no personal files or .venv are staged
   git commit -m "Initial release: KhemSAR v1.0.0"
   git remote add origin https://github.com/Sbolivar16/KhemSAR.git
   git push -u origin main
   ```

## Step 2: Connect GitHub to Zenodo
1. Log in to [https://zenodo.org](https://zenodo.org) using **"Log in with GitHub"** (use your **Sbolivar16** account).
2. Go to **Account → GitHub** (`https://zenodo.org/account/settings/github/`).
3. Locate **`Sbolivar16/KhemSAR`** and toggle the switch **ON**. *(Zenodo automatically reads `.zenodo.json` and `CITATION.cff` from your repository).*

## Step 3: Publish Release `v1.0.0` on GitHub to Mint the DOI
1. On GitHub, open `https://github.com/Sbolivar16/KhemSAR/releases/new`.
2. Set Tag version: **`v1.0.0`**, Release title: **`KhemSAR v1.0.0 — Initial Scientific Release`**.
3. Click **Publish release**.
4. Within 1–2 minutes, Zenodo will archive the release and mint your official **DOI** (e.g. `10.5281/zenodo.XXXXXXX`).
5. Copy the Zenodo DOI badge into `README.md` and `CITATION.cff` (`doi: "10.5281/zenodo.XXXXXXX"`).
