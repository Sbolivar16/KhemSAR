"""BindingDB REST API connector for protein-ligand affinity retrieval."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import BioactivityRecord, ConnectorResult, build_async_client

BINDINGDB_API = "https://bindingdb.org/rest"


async def fetch_bindingdb_affinities(
    uniprot_id: str | None = None,
    pdb_id: str | None = None,
    limit: int = 500,
) -> ConnectorResult:
    """Query BindingDB affinities by UniProt accession or PDB ID."""
    if not uniprot_id and not pdb_id:
        return ConnectorResult(source="BindingDB", ok=True, records=[], metadata={"note": "Requires UniProt or PDB ID."})

    try:
        url = (
            f"{BINDINGDB_API}/getLigandsByUniprod"
            if False
            else f"{BINDINGDB_API}/getLigandsByUniprot"
        )
        params: dict[str, Any] = {"response": "application/json"}
        if uniprot_id:
            params["uniprot"] = uniprot_id.strip()
        else:
            url = f"{BINDINGDB_API}/getLigandsByPDBs"
            params["pdb"] = pdb_id.strip().upper()

        async with build_async_client(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code >= 400:
                return ConnectorResult(source="BindingDB", ok=False, error=f"HTTP {resp.status_code}")
            data = resp.json()

        affinities = (
            data.get("getLigandsByUniprotResponse", {}).get("affinities")
            or data.get("getLigandsByPDBsResponse", {}).get("affinities")
            or []
        )
        records: list[dict[str, Any]] = []
        for item in affinities[:limit]:
            smiles = item.get("smile") or item.get("smiles")
            val_raw = item.get("affinity")
            atype = item.get("affinity_type") or "IC50"
            if not smiles or val_raw is None:
                continue
            val_str = str(val_raw).strip()
            relation = "="
            if val_str.startswith((">", "<")):
                relation = val_str[0]
                val_str = val_str[1:].strip()
            try:
                fval = float(val_str)
            except ValueError:
                continue
            records.append(
                BioactivityRecord(
                    compound_id=str(item.get("monomerid", "")),
                    name=f"BDBM_{item.get('monomerid', '')}",
                    smiles=smiles,
                    standard_type=atype,
                    standard_relation=relation,
                    standard_value=fval,
                    standard_units="nM",
                    source="BindingDB",
                    assay_id=f"BDB_{uniprot_id or pdb_id}",
                    target_name=item.get("query", "") or (uniprot_id or pdb_id or ""),
                    uniprot_id=uniprot_id or "",
                ).to_dict()
            )
        return ConnectorResult(source="BindingDB", ok=True, records=records, metadata={"count": len(records)})
    except Exception as exc:
        return ConnectorResult(source="BindingDB", ok=False, error=str(exc))
