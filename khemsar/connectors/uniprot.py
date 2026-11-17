"""UniProt REST API connector for therapeutic target metadata and PDB cross-references."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import ConnectorResult, build_async_client

UNIPROT_API = "https://rest.uniprot.org/uniprotkb"


async def search_uniprot(query: str, organism_id: int = 9606, limit: int = 5) -> ConnectorResult:
    clean_q = (query or "").strip()
    if not clean_q:
        return ConnectorResult(source="UniProt", ok=True, records=[])
    try:
        import re

        if re.fullmatch(r"[A-NR-Z][0-9][A-Z0-9]{3}[0-9]|[OPQ][0-9][A-Z0-9]{3}[0-9]", clean_q.upper()):
            q = f"accession:{clean_q.upper()}"
        else:
            q = f"({clean_q}) AND reviewed:true"
            if organism_id:
                q += f" AND organism_id:{organism_id}"
        async with build_async_client() as client:
            resp = await client.get(
                f"{UNIPROT_API}/search",
                params={"query": q, "size": limit, "format": "json"},
            )
            if resp.status_code != 200:
                return ConnectorResult(source="UniProt", ok=False, error=f"HTTP {resp.status_code}")
            results = resp.json().get("results", [])
            parsed: list[dict[str, Any]] = []
            for entry in results:
                acc = entry.get("primaryAccession", "")
                pname = (
                    entry.get("proteinDescription", {})
                    .get("recommendedName", {})
                    .get("fullName", {})
                    .get("value", "")
                )
                genes = [g.get("geneName", {}).get("value") for g in entry.get("genes", []) if g.get("geneName")]
                pdbs = [
                    x.get("id")
                    for x in entry.get("uniProtKBCrossReferences", [])
                    if x.get("database") == "PDB"
                ][:10]
                parsed.append(
                    {
                        "uniprot_id": acc,
                        "protein_name": pname,
                        "genes": genes,
                        "organism": entry.get("organism", {}).get("scientificName", ""),
                        "pdb_ids": pdbs,
                    }
                )
            return ConnectorResult(source="UniProt", ok=True, records=parsed, metadata={"count": len(parsed)})
    except Exception as exc:
        return ConnectorResult(source="UniProt", ok=False, error=str(exc))
