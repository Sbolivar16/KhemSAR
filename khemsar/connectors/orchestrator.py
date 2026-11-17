"""Multi-database scientific search orchestrator across all 10 KhemSAR sources."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from khemsar.connectors import (
    alphafold,
    bindingdb,
    chembl,
    coconut,
    gtopdb,
    opentargets,
    pubchem,
    rcsb_pdb,
    unichem,
    uniprot,
)


async def run_multidb_search(
    target_query: str,
    chembl_target_id: str | None = None,
    pdb_id: str | None = None,
    pubchem_aid: str | None = None,
    standard_types: tuple[str, ...] = ("IC50", "Ki", "Kd", "EC50"),
    min_confidence: int = 7,
    max_records: int = 2000,
    include_sources: list[str] | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Query ChEMBL, PubChem, BindingDB, GtoPdb, UniProt, RCSB PDB, AlphaFold, Open Targets & COCONUT."""
    enabled = set(
        include_sources
        or [
            "chembl",
            "pubchem",
            "bindingdb",
            "gtopdb",
            "uniprot",
            "rcsb_pdb",
            "alphafold",
            "opentargets",
            "coconut",
        ]
    )

    # 0. Clean inputs; if target_query is blank but PDB ID was provided (e.g. 2FOM), resolve target from PDB
    clean_query = (target_query or "").strip()
    clean_pdb = (pdb_id or "").strip().upper() or None
    clean_chembl = (chembl_target_id or "").strip().upper() or None
    pdb_meta: dict[str, Any] = {}
    if clean_pdb and not clean_query:
        pdb_meta = await rcsb_pdb.resolve_pdb_target_info(clean_pdb)
        clean_query = (pdb_meta.get("macromolecule_name") or pdb_meta.get("title") or clean_pdb).strip()

    if not clean_query and not clean_chembl and not clean_pdb:
        return {
            "query": "",
            "resolved_target": {"chembl_target_id": "", "uniprot_id": "", "chembl_candidates": [], "uniprot": []},
            "source_status": [],
            "bioactivities": [],
            "pdb_structures": [],
            "alphafold": [],
            "opentargets": [],
            "coconut_natural_products": [],
            "unichem_available": hasattr(unichem, "lookup_unichem_by_inchikey"),
        }

    # 1. Safely resolve UniProt / ChEMBL target metadata in parallel (never raise on API failure)
    pdb_uniprot = (pdb_meta.get("uniprot_ids") or [""])[0] if pdb_meta else ""
    uniprot_q = pdb_uniprot or clean_query

    async def _safe_uniprot() -> Any:
        if "uniprot" not in enabled or not uniprot_q:
            return None
        try:
            return await uniprot.search_uniprot(uniprot_q, organism_id=0 if pdb_uniprot else 9606, limit=3)
        except Exception:
            return None

    async def _safe_chembl_targets() -> list[dict[str, Any]]:
        if "chembl" not in enabled or clean_chembl:
            return []
        try:
            if pdb_uniprot:
                by_up = await chembl.search_targets_by_uniprot(pdb_uniprot, limit=5)
                if by_up:
                    return by_up
            return await chembl.search_targets(clean_query, limit=5) if clean_query else []
        except Exception:
            return []

    if progress_cb:
        progress_cb(12, "Resolving target metadata (PDB / UniProt / ChEMBL)...")
    uniprot_res, chembl_targets = await asyncio.gather(_safe_uniprot(), _safe_chembl_targets())

    resolved_chembl_id = clean_chembl or (
        chembl_targets[0]["target_chembl_id"] if chembl_targets else None
    )
    resolved_uniprot_id = pdb_uniprot
    if not resolved_uniprot_id and uniprot_res and uniprot_res.records:
        resolved_uniprot_id = uniprot_res.records[0].get("uniprot_id", "")
    elif not resolved_uniprot_id and chembl_targets:
        resolved_uniprot_id = chembl_targets[0].get("uniprot_id", "")

    per_db_limit = max(100, min(max_records, 3000))

    tasks: dict[str, Any] = {}
    if "chembl" in enabled and resolved_chembl_id:
        tasks["chembl"] = chembl.fetch_bioactivities(
            target_chembl_id=resolved_chembl_id,
            standard_types=standard_types,
            min_confidence=min_confidence,
            limit=per_db_limit,
        )
    if "pubchem" in enabled and (clean_query or pubchem_aid):
        tasks["pubchem"] = pubchem.fetch_pubchem_bioactivities(
            gene_or_query=clean_query,
            assay_id=pubchem_aid,
            limit=min(per_db_limit, 500),
        )
    if "bindingdb" in enabled and (resolved_uniprot_id or clean_pdb):
        tasks["bindingdb"] = bindingdb.fetch_bindingdb_affinities(
            uniprot_id=resolved_uniprot_id or None,
            pdb_id=clean_pdb,
            limit=min(per_db_limit, 500),
        )
    if "gtopdb" in enabled and clean_query:
        tasks["gtopdb"] = gtopdb.fetch_gtopdb_interactions(clean_query, limit=100)
    if "rcsb_pdb" in enabled and (clean_pdb or clean_query):
        tasks["rcsb_pdb"] = rcsb_pdb.search_pdb_structures(clean_pdb or clean_query, limit=6)
    if "alphafold" in enabled and resolved_uniprot_id:
        tasks["alphafold"] = alphafold.fetch_alphafold_entry(resolved_uniprot_id)
    if "opentargets" in enabled and clean_query:
        tasks["opentargets"] = opentargets.fetch_opentargets_evidence(clean_query)
    if "coconut" in enabled and clean_query:
        tasks["coconut"] = coconut.search_coconut_natural_products(clean_query, limit=8)

    total_tasks = max(1, len(tasks))
    done_count = 0
    results_map: dict[str, Any] = {}

    async def _run_named(key: str, coro: Any) -> None:
        nonlocal done_count
        try:
            res = await coro
            results_map[key] = res.to_dict() if hasattr(res, "to_dict") else res
        except Exception as exc:
            results_map[key] = {"source": key, "ok": False, "error": str(exc), "records": []}
        done_count += 1
        if progress_cb:
            pct = 20 + int(75 * (done_count / total_tasks))
            progress_cb(pct, f"Querying databases ({done_count}/{total_tasks}): {key} ✓")

    await asyncio.gather(*(_run_named(k, v) for k, v in tasks.items()))

    bioactivities: list[dict[str, Any]] = []
    source_status: list[dict[str, Any]] = []
    for db_key in ("chembl", "pubchem", "bindingdb", "gtopdb"):
        if db_key in results_map:
            entry = results_map[db_key]
            recs = entry.get("records", [])
            bioactivities.extend(recs)
            source_status.append(
                {
                    "source": entry.get("source", db_key),
                    "ok": entry.get("ok", True),
                    "count": len(recs),
                    "error": entry.get("error", ""),
                }
            )

    if len(bioactivities) > max_records:
        bioactivities = bioactivities[:max_records]

    pdb_hits = results_map.get("rcsb_pdb", [])
    if isinstance(pdb_hits, dict):
        pdb_hits = []
    if not pdb_hits and clean_pdb:
        pdb_hits = [pdb_meta] if pdb_meta else [{"pdb_id": clean_pdb, "title": "Requested PDB"}]
    if not pdb_hits and uniprot_res and uniprot_res.records:
        pdb_hits = [{"pdb_id": pid, "title": "UniProt cross-referenced PDB"} for pid in uniprot_res.records[0].get("pdb_ids", [])]

    return {
        "query": clean_query,
        "resolved_target": {
            "chembl_target_id": resolved_chembl_id or "",
            "uniprot_id": resolved_uniprot_id,
            "pdb_meta": pdb_meta,
            "chembl_candidates": chembl_targets,
            "uniprot": uniprot_res.records if uniprot_res else [],
        },
        "source_status": source_status,
        "bioactivities": bioactivities,
        "pdb_structures": pdb_hits,
        "alphafold": results_map.get("alphafold", {}).get("records", []),
        "opentargets": results_map.get("opentargets", {}).get("records", []),
        "coconut_natural_products": results_map.get("coconut", {}).get("records", []),
        "unichem_available": hasattr(unichem, "lookup_unichem_by_inchikey"),
    }
