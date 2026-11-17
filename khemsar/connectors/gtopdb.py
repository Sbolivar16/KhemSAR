"""IUPHAR/BPS Guide to PHARMACOLOGY (GtoPdb) REST API connector."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import BioactivityRecord, ConnectorResult, build_async_client

GTOPDB_API = "https://www.guidetopharmacology.org/services"


async def fetch_gtopdb_interactions(query: str, limit: int = 100) -> ConnectorResult:
    try:
        async with build_async_client() as client:
            t_resp = await client.get(f"{GTOPDB_API}/targets", params={"name": query})
            if t_resp.status_code != 200:
                return ConnectorResult(source="GtoPdb", ok=True, records=[])
            targets = t_resp.json()
            if not isinstance(targets, list) or not targets:
                return ConnectorResult(source="GtoPdb", ok=True, records=[])
            target_id = targets[0].get("targetId")
            target_name = targets[0].get("name", query)
            i_resp = await client.get(f"{GTOPDB_API}/targets/{target_id}/interactions")
            if i_resp.status_code != 200:
                return ConnectorResult(source="GtoPdb", ok=True, records=[])
            interactions = i_resp.json()
            records: list[dict[str, Any]] = []
            for item in interactions[:limit]:
                lig_id = item.get("ligandId")
                if not lig_id:
                    continue
                aff_med = item.get("affinityMedian")
                aff_type = item.get("affinityType", "pKi")
                if aff_med is None:
                    continue
                lig_resp = await client.get(f"{GTOPDB_API}/ligands/{lig_id}")
                if lig_resp.status_code != 200:
                    continue
                lig = lig_resp.json()
                smiles = lig.get("smiles")
                if not smiles:
                    continue
                # GtoPdb reports affinities on p-scale (pKi/pIC50/pKd)
                try:
                    p_val = float(aff_med)
                    nm_val = (10 ** (-p_val)) * 1e9
                except (TypeError, ValueError):
                    continue
                stype = aff_type.lstrip("p") if aff_type.startswith("p") else aff_type
                records.append(
                    BioactivityRecord(
                        compound_id=f"GTOPDB_{lig_id}",
                        name=lig.get("name", f"GTOPDB_{lig_id}"),
                        smiles=smiles,
                        standard_type=stype or "Ki",
                        standard_relation="=",
                        standard_value=round(nm_val, 4),
                        standard_units="nM",
                        source="GtoPdb",
                        assay_id=f"GTOPDB_T{target_id}",
                        assay_description=f"IUPHAR curated interaction ({item.get('action', '')})",
                        target_name=target_name,
                    ).to_dict()
                )
            return ConnectorResult(
                source="GtoPdb",
                ok=True,
                records=records,
                metadata={"target_id": target_id, "target_name": target_name, "count": len(records)},
            )
    except Exception as exc:
        return ConnectorResult(source="GtoPdb", ok=False, error=str(exc))
