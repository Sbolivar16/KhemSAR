"""COCONUT Open Natural Products REST API connector."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import ConnectorResult, build_async_client

COCONUT_API = "https://coconut.naturalproducts.net/api/search"


async def search_coconut_natural_products(smiles_or_name: str, limit: int = 10) -> ConnectorResult:
    try:
        async with build_async_client() as client:
            resp = await client.get(
                f"{COCONUT_API}/simple",
                params={"query": smiles_or_name, "limit": limit},
            )
            if resp.status_code >= 400:
                return ConnectorResult(source="COCONUT", ok=True, records=[], metadata={"note": f"HTTP {resp.status_code}"})
            data = resp.json()
            items = data.get("data", data if isinstance(data, list) else [])
            records: list[dict[str, Any]] = []
            for item in items[:limit]:
                smi = item.get("canonical_smiles") or item.get("smiles")
                if not smi:
                    continue
                records.append(
                    {
                        "coconut_id": item.get("identifier") or item.get("coconut_id", ""),
                        "name": item.get("name", ""),
                        "smiles": smi,
                        "molecular_weight": item.get("molecular_weight"),
                        "np_likeness": item.get("np_likeness"),
                    }
                )
            return ConnectorResult(source="COCONUT", ok=True, records=records, metadata={"count": len(records)})
    except Exception as exc:
        return ConnectorResult(source="COCONUT", ok=False, error=str(exc))
