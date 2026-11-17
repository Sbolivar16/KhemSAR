"""End-to-end FastAPI, trilingual AI Tutor, AI Copilot, and Cloud integration tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from khemsar.main import app


def test_end_to_end_api_and_tutor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KHEMSAR_WORKSPACE", str(tmp_path / "workspaces"))
    client = TestClient(app)

    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["app"] == "KhemSAR"

    for lang in ("es", "en", "pt"):
        loc = client.get(f"/api/locales/{lang}")
        assert loc.status_code == 200
        cur = client.get(f"/api/tutor/curriculum?lang={lang}")
        assert cur.status_code == 200
        assert len(cur.json()["lessons"]) == 5

    intent = client.post(
        "/api/ai/parse-intent",
        json={"description": "Busco inhibidores de COX-2 con IC50 < 100 nM y estructura PDB 3LN1"},
    )
    assert intent.status_code == 200
    assert intent.json()["target_query"] == "PTGS2"
    assert intent.json()["pdb_id"] == "3LN1"

    proj = client.post("/api/projects", json={"name": "Test_COX2", "target": "PTGS2"}).json()
    pid = proj["project_id"]

    demo = client.post(f"/api/projects/{pid}/demo")
    assert demo.status_code == 200

    curate = client.post(f"/api/projects/{pid}/curate", json={"target_endpoint": "IC50"})
    assert curate.status_code == 200
    assert curate.json()["report"]["final_count"] >= 40

    train = client.post(
        f"/api/projects/{pid}/qsar/train",
        json={"feature_mode": "physchem", "split_method": "stratified", "y_scrambling_permutations": 10, "algorithms": ["RandomForest"]},
    )
    assert train.status_code == 200
    assert "test_ext" in train.json()["linear_fit"]

    svg_resp = client.get("/api/molecule/svg", params={"smiles": "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1"})
    assert svg_resp.status_code == 200
    assert "<svg" in svg_resp.text

    pdb_3d = client.get("/api/molecule/3d-pdb", params={"smiles": "O=C(O)Cc1ccccc1Nc1c(Cl)cccc1Cl"})
    assert pdb_3d.status_code == 200
    assert "ATOM" in pdb_3d.json()["pdb_block"] or "HETATM" in pdb_3d.json()["pdb_block"]

    sar = client.post(f"/api/projects/{pid}/sar/analyze", json={})
    assert sar.status_code == 200

    tutor_resp = client.post(
        "/api/tutor/ask",
        json={"question": "Interpreta mi estudio activo", "lang": "es", "project_id": pid},
    )
    assert tutor_resp.status_code == 200
    assert "Q^2" in tutor_resp.json()["answer"] or "Q2" in tutor_resp.json()["answer"]

    dn = client.post(f"/api/projects/{pid}/denovo/generate", json={"n_top_seeds": 4, "n_brics_samples": 10, "max_candidates": 8})
    assert dn.status_code == 200
    assert dn.json()["n_generated"] >= 2

    plots = client.post(f"/api/projects/{pid}/plots/generate", json={"dpi": 150, "plot_lang": "en"})
    assert plots.status_code == 200
    assert "qsar_parity" in plots.json()["figures"]

    exp3d = client.post(f"/api/projects/{pid}/export-3d", json={"max_molecules": 4})
    assert exp3d.status_code == 200
    zip_dl = client.get(f"/api/projects/{pid}/download/{exp3d.json()['download_zip']}")
    assert zip_dl.status_code == 200
    assert len(zip_dl.content) > 500

    colab = client.get(f"/api/projects/{pid}/colab-notebook")
    assert colab.status_code == 200
    assert "nbformat" in colab.json()

    oauth = client.post("/api/cloud/oauth-url", json={"provider": "gdrive", "client_id": "demo-client-id"})
    assert oauth.status_code == 200
    assert "accounts.google.com" in oauth.json()["auth_url"]

    from khemsar.cloud.storage import build_google_drive_direct_download_url

    dl = build_google_drive_direct_download_url("https://drive.google.com/file/d/1AbCdEfGhIjK/view?usp=sharing")
    assert dl == "https://drive.google.com/uc?export=download&id=1AbCdEfGhIjK"

    reveal = client.post("/api/cloud/reveal-bundle", json={"project_id": pid, "open_local": False})
    assert reveal.status_code == 200
    assert reveal.json()["bundle_name"].endswith(".qsarproj.zip")

    progress = client.get(f"/api/projects/{pid}/progress")
    assert progress.status_code == 200
    prog_data = progress.json()
    assert prog_data["project_id"] == pid
    assert prog_data["percent"] == 100
    assert prog_data["active"] is False
    assert isinstance(prog_data["detail"], str) and len(prog_data["detail"]) > 0

    empty_search = client.post(f"/api/projects/{pid}/search", json={"target_query": "", "pdb_id": ""})
    assert empty_search.status_code == 400
