"""RCSB PDB connector with 3D retrieval, receptor cleaning, and docking box estimation."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import build_async_client

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA = "https://data.rcsb.org/rest/v1/core/entry"
RCSB_POLYMER = "https://data.rcsb.org/rest/v1/core/polymer_entity"
RCSB_FILES = "https://files.rcsb.org/download"

SOLVENT_AND_COMMON_IONS = {
    "HOH", "WAT", "DOD", "NA", "CL", "K", "MG", "CA", "ZN", "MN", "FE", "CU",
    "SO4", "PO4", "EDO", "GOL", "PEG", "DMS", "ACE", "ACT", "BME", "MPD",
}
PROSTHETIC_AND_GLYCAN_HETATMS = {
    "HEM", "HEC", "HEA", "FAD", "FMN", "NAD", "NAP", "NDP", "ATP", "ADP", "AMP",
    "GTP", "GDP", "GMP", "COA", "SAM", "SAH", "PLP", "B12", "NAG", "MAN", "BMA",
    "FUC", "GAL", "SIA", "BOG", "OCT",
}


async def resolve_pdb_target_info(pdb_id: str) -> dict[str, Any]:
    """Resolve protein name, UniProt accessions, and title from an RCSB PDB ID."""
    clean_id = (pdb_id or "").strip().upper()
    if not clean_id:
        return {}
    info_out: dict[str, Any] = {"pdb_id": clean_id, "title": "", "macromolecule_name": "", "uniprot_ids": [], "organism": ""}
    try:
        async with build_async_client(timeout=15.0) as client:
            r_entry = await client.get(f"{RCSB_DATA}/{clean_id}")
            if r_entry.status_code == 200:
                entry = r_entry.json()
                info_out["title"] = entry.get("struct", {}).get("title", "")
            r_poly = await client.get(f"{RCSB_POLYMER}/{clean_id}/1")
            if r_poly.status_code == 200:
                poly = r_poly.json()
                info_out["macromolecule_name"] = poly.get("rcsb_polymer_entity", {}).get("pdbx_description", "")
                cont = poly.get("rcsb_polymer_entity_container_identifiers", {})
                uniprots = list(cont.get("uniprot_ids") or [])
                for ref in cont.get("reference_sequence_identifiers") or []:
                    if str(ref.get("database_name", "")).lower() == "uniprot" and ref.get("database_accession"):
                        acc = str(ref["database_accession"])
                        if acc not in uniprots:
                            uniprots.append(acc)
                info_out["uniprot_ids"] = uniprots
                orgs = poly.get("rcsb_entity_source_organism") or []
                if orgs:
                    info_out["organism"] = orgs[0].get("ncbi_scientific_name", "")
    except Exception:
        pass
    return info_out


async def search_pdb_structures(query: str, limit: int = 8) -> list[dict[str, Any]]:
    if not (query or "").strip():
        return []
    payload = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query.strip()},
        },
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": limit}},
    }
    try:
        async with build_async_client() as client:
            resp = await client.post(RCSB_SEARCH, json=payload)
            if resp.status_code != 200:
                return []
            hits = resp.json().get("result_set", [])
            results: list[dict[str, Any]] = []
            for hit in hits[:limit]:
                pdb_id = hit.get("identifier", "")
                meta: dict[str, Any] = {"pdb_id": pdb_id, "score": hit.get("score")}
                info_resp = await client.get(f"{RCSB_DATA}/{pdb_id}")
                if info_resp.status_code == 200:
                    info = info_resp.json()
                    meta["title"] = info.get("struct", {}).get("title", "")
                    res_list = info.get("rcsb_entry_info", {}).get("resolution_combined") or []
                    meta["resolution_angstrom"] = res_list[0] if res_list else None
                    meta["method"] = info.get("exptl", [{}])[0].get("method", "")
                results.append(meta)
            return results
    except Exception:
        return []


async def fetch_pdb_text(pdb_id: str) -> str:
    clean_id = pdb_id.strip().upper()
    async with build_async_client(timeout=30.0) as client:
        resp = await client.get(f"{RCSB_FILES}/{clean_id}.pdb")
        resp.raise_for_status()
        return resp.text


def prepare_receptor_and_docking_box(
    pdb_text: str,
    chain_id: str | None = None,
    remove_waters: bool = True,
    padding: float = 8.0,
) -> dict[str, Any]:
    """Separate clean receptor ATOM lines from co-crystallized ligand and estimate docking grid box."""
    protein_lines: list[str] = []
    ligand_atoms_by_res: dict[tuple[str, str, str], list[tuple[str, float, float, float]]] = {}

    for line in pdb_text.splitlines():
        record = line[:6].strip()
        if record == "ATOM":
            chain = line[21].strip() or "A"
            if chain_id and chain != chain_id:
                continue
            protein_lines.append(line)
        elif record == "TER" and (not chain_id or (len(line) > 21 and line[21].strip() == chain_id)):
            protein_lines.append(line)
        elif record == "HETATM":
            resname = line[17:20].strip()
            chain = line[21].strip() or "A"
            resseq = line[22:26].strip()
            if remove_waters and resname in SOLVENT_AND_COMMON_IONS:
                continue
            if resname in SOLVENT_AND_COMMON_IONS:
                continue
            if chain_id and chain != chain_id:
                continue
            if resname in PROSTHETIC_AND_GLYCAN_HETATMS:
                # Keep essential cofactors (e.g. heme in COX-2/CYPs) in the receptor; do not mistake for drug ligand
                protein_lines.append(line)
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            ligand_atoms_by_res.setdefault((resname, chain, resseq), []).append((line, x, y, z))

    protein_lines.append("END")

    # Select largest organic co-crystal ligand by heavy atom count
    best_key = None
    best_atoms: list[tuple[str, float, float, float]] = []
    for key, atoms in ligand_atoms_by_res.items():
        if len(atoms) > len(best_atoms):
            best_key = key
            best_atoms = atoms

    ligand_pdb = ""
    docking_box: dict[str, Any] = {}
    if best_atoms:
        ligand_pdb = "\n".join(a[0] for a in best_atoms) + "\nEND"
        xs = [a[1] for a in best_atoms]
        ys = [a[2] for a in best_atoms]
        zs = [a[3] for a in best_atoms]
        cx = round((min(xs) + max(xs)) / 2.0, 3)
        cy = round((min(ys) + max(ys)) / 2.0, 3)
        cz = round((min(zs) + max(zs)) / 2.0, 3)
        sx = round(max(16.0, (max(xs) - min(xs)) + padding), 2)
        sy = round(max(16.0, (max(ys) - min(ys)) + padding), 2)
        sz = round(max(16.0, (max(zs) - min(zs)) + padding), 2)
        docking_box = {
            "ligand_resname": best_key[0] if best_key else "",
            "ligand_chain": best_key[1] if best_key else "",
            "ligand_atom_count": len(best_atoms),
            "center_x": cx,
            "center_y": cy,
            "center_z": cz,
            "size_x": sx,
            "size_y": sy,
            "size_z": sz,
        }

    return {
        "receptor_pdb": "\n".join(protein_lines),
        "cocrystal_ligand_pdb": ligand_pdb,
        "docking_box": docking_box,
        "protein_atom_count": sum(1 for l in protein_lines if l.startswith("ATOM")),
    }
