"""EMBL-EBI UniChem REST API connector for cross-database InChIKey mapping."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import ConnectorResult, build_async_client

UNICHEM_API = "https://www.ebi.ac.uk/unichem/rest"


async def lookup_unichem_by_inchikey(inchikey: str) -> ConnectorResult:
    if not inchikey:
        return ConnectorResult(source="UniChem", ok=True, records=[])
    try:
        async with build_async_client() as client:
            resp = await client.get(f"{UNICHEM_API}/inchikey/{inchikey.strip()}")
            if resp.status_code == 404:
                return ConnectorResult(source="UniChem", ok=True, records=[])
            resp.raise_for_status()
            rows = resp.json()
            mapped: list[dict[str, Any]] = [
                {"src_id": r.get("src_id"), "src_compound_id": r.get("src_compound_id")}
                for r in (rows if isinstance(rows, list) else [])
            ]
            return ConnectorResult(source="UniChem", ok=True, records=mapped)
    except Exception as exc:
        return ConnectorResult(source="UniChem", ok=False, error=str(exc))
