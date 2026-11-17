"""AlphaFold Protein Structure Database connector."""

from __future__ import annotations

from khemsar.connectors.base import ConnectorResult, build_async_client

ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction"


async def fetch_alphafold_entry(uniprot_id: str) -> ConnectorResult:
    if not uniprot_id:
        return ConnectorResult(source="AlphaFold DB", ok=True, records=[], metadata={"note": "No UniProt ID provided."})
    try:
        async with build_async_client() as client:
            resp = await client.get(f"{ALPHAFOLD_API}/{uniprot_id.strip().upper()}")
            if resp.status_code == 404:
                return ConnectorResult(source="AlphaFold DB", ok=True, records=[])
            resp.raise_for_status()
            data = resp.json()
            entries = data if isinstance(data, list) else [data]
            simplified = [
                {
                    "entry_id": e.get("entryId", ""),
                    "uniprot_accession": e.get("uniprotAccession", ""),
                    "pdb_url": e.get("pdbUrl", ""),
                    "cif_url": e.get("cifUrl", ""),
                    "pae_doc_url": e.get("paeDocUrl", ""),
                }
                for e in entries[:3]
            ]
            return ConnectorResult(source="AlphaFold DB", ok=True, records=simplified)
    except Exception as exc:
        return ConnectorResult(source="AlphaFold DB", ok=False, error=str(exc))
