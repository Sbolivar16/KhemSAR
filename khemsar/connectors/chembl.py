"""ChEMBL REST API connector for target lookup and bioactivity retrieval."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import BioactivityRecord, ConnectorResult, build_async_client

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"


async def search_targets(query: str, organism: str = "Homo sapiens", limit: int = 8) -> list[dict[str, Any]]:
    if not (query or "").strip():
        return []
    try:
        async with build_async_client() as client:
            resp = await client.get(
                f"{CHEMBL_API}/target/search.json",
                params={"q": query.strip(), "limit": limit},
            )
            if resp.status_code >= 400:
                return []
            targets = resp.json().get("targets", [])
            return _format_targets(targets, organism=organism, limit=limit)
    except Exception:
        return []


async def search_targets_by_uniprot(uniprot_id: str, limit: int = 5) -> list[dict[str, Any]]:
    if not (uniprot_id or "").strip():
        return []
    try:
        async with build_async_client() as client:
            resp = await client.get(
                f"{CHEMBL_API}/target.json",
                params={"target_components__accession": uniprot_id.strip().upper(), "limit": limit},
            )
            if resp.status_code >= 400:
                return []
            targets = resp.json().get("targets", [])
            return _format_targets(targets, organism="", limit=limit)
    except Exception:
        return []


def _format_targets(targets: list[dict[str, Any]], organism: str, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in targets:
        org = item.get("organism", "")
        if organism and organism.lower() not in org.lower() and len(targets) > 3:
            continue
        uniprot = ""
        for comp in item.get("target_components", []) or []:
            acc = comp.get("accession")
            if acc:
                uniprot = acc
                break
        results.append(
            {
                "target_chembl_id": item.get("target_chembl_id", ""),
                "pref_name": item.get("pref_name", ""),
                "target_type": item.get("target_type", ""),
                "organism": org,
                "uniprot_id": uniprot,
            }
        )
    return results or [
        {
            "target_chembl_id": item.get("target_chembl_id", ""),
            "pref_name": item.get("pref_name", ""),
            "target_type": item.get("target_type", ""),
            "organism": item.get("organism", ""),
            "uniprot_id": "",
        }
        for item in targets[:limit]
    ]


async def fetch_bioactivities(
    target_chembl_id: str | None = None,
    query: str | None = None,
    standard_types: tuple[str, ...] = ("IC50", "Ki", "Kd", "EC50"),
    min_confidence: int = 7,
    limit: int = 1000,
) -> ConnectorResult:
    try:
        resolved_id = target_chembl_id
        target_meta: dict[str, Any] = {}
        if not resolved_id and query:
            matches = await search_targets(query, limit=5)
            if not matches:
                return ConnectorResult(source="ChEMBL", ok=True, records=[], metadata={"note": "No ChEMBL target matched."})
            target_meta = matches[0]
            resolved_id = target_meta["target_chembl_id"]

        if not resolved_id:
            return ConnectorResult(source="ChEMBL", ok=False, error="Missing ChEMBL target ID or query.")

        records: list[dict[str, Any]] = []
        offset = 0
        page_size = min(500, max(50, limit))
        async with build_async_client(timeout=35.0) as client:
            while len(records) < limit:
                params = {
                    "target_chembl_id": resolved_id,
                    "standard_type__in": ",".join(standard_types),
                    "limit": min(page_size, limit - len(records)),
                    "offset": offset,
                }
                resp = await client.get(f"{CHEMBL_API}/activity.json", params=params)
                resp.raise_for_status()
                payload = resp.json()
                activities = payload.get("activities", [])
                if not activities:
                    break
                for act in activities:
                    smiles = act.get("canonical_smiles")
                    val = act.get("standard_value")
                    if not smiles or val is None:
                        continue
                    if act.get("data_validity_comment") not in (None, ""):
                        continue
                    try:
                        fval = float(val)
                    except (TypeError, ValueError):
                        continue
                    rec = BioactivityRecord(
                        compound_id=act.get("molecule_chembl_id", ""),
                        name=act.get("molecule_pref_name") or act.get("molecule_chembl_id", ""),
                        smiles=smiles,
                        standard_type=act.get("standard_type", ""),
                        standard_relation=act.get("standard_relation") or "=",
                        standard_value=fval,
                        standard_units=act.get("standard_units") or "nM",
                        year=act.get("document_year"),
                        source="ChEMBL",
                        assay_id=act.get("assay_chembl_id", ""),
                        assay_description=act.get("assay_description", ""),
                        confidence_score=act.get("confidence_score"),
                        target_name=act.get("target_pref_name") or target_meta.get("pref_name", ""),
                        target_chembl_id=resolved_id,
                        uniprot_id=target_meta.get("uniprot_id", ""),
                    )
                    if rec.confidence_score is not None and rec.confidence_score < min_confidence:
                        continue
                    records.append(rec.to_dict())
                if not payload.get("page_meta", {}).get("next"):
                    break
                offset += len(activities)

        return ConnectorResult(
            source="ChEMBL",
            ok=True,
            records=records,
            metadata={"target_chembl_id": resolved_id, "target": target_meta, "count": len(records)},
        )
    except Exception as exc:
        return ConnectorResult(source="ChEMBL", ok=False, error=str(exc))
