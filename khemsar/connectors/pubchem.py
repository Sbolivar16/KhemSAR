"""PubChem PUG-REST connector for BioAssay and compound bioactivity lookup."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from khemsar.connectors.base import BioactivityRecord, ConnectorResult, build_async_client

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


async def fetch_pubchem_bioactivities(
    gene_or_query: str,
    assay_id: str | None = None,
    limit: int = 500,
) -> ConnectorResult:
    """Fetch PubChem BioAssay concise records by AID or target gene/name."""
    try:
        async with build_async_client(timeout=30.0) as client:
            aids: list[str] = []
            if assay_id:
                aids = [str(assay_id).replace("AID", "").strip()]
            else:
                # Try gene symbol lookup first, then target name search via NCBI E-utilities
                clean_q = quote(gene_or_query.strip())
                r = await client.get(f"{PUBCHEM_BASE}/assay/target/genesymbol/{clean_q}/aids/JSON")
                if r.status_code == 200:
                    info = r.json().get("InformationList", {}).get("Information", [])
                    for entry in info:
                        aids.extend([str(a) for a in entry.get("AID", [])[:5]])
                if not aids:
                    esearch = await client.get(
                        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                        params={"db": "pcassay", "term": gene_or_query, "retmode": "json", "retmax": 5},
                    )
                    if esearch.status_code == 200:
                        aids = esearch.json().get("esearchresult", {}).get("idlist", [])

            if not aids:
                return ConnectorResult(source="PubChem", ok=True, records=[], metadata={"note": "No matching PubChem AIDs."})

            records: list[dict[str, Any]] = []
            for aid in aids[:3]:
                if len(records) >= limit:
                    break
                concise = await client.get(f"{PUBCHEM_BASE}/assay/aid/{aid}/concise/JSON")
                if concise.status_code != 200:
                    continue
                table = concise.json().get("Table", {})
                cols = table.get("Columns", {}).get("Column", [])
                rows = table.get("Row", [])
                col_idx = {name: i for i, name in enumerate(cols)}
                cid_i = col_idx.get("CID")
                act_name_i = col_idx.get("Activity Name")
                act_val_i = col_idx.get("Activity Value [uM]")
                outcome_i = col_idx.get("Activity Outcome")

                cids: list[str] = []
                parsed_rows: list[tuple[str, str, float, str]] = []
                for row in rows:
                    cells = row.get("Cell", [])
                    if cid_i is None or cid_i >= len(cells) or not cells[cid_i]:
                        continue
                    cid = str(cells[cid_i])
                    act_name = str(cells[act_name_i]) if act_name_i is not None and act_name_i < len(cells) else "IC50"
                    val_raw = cells[act_val_i] if act_val_i is not None and act_val_i < len(cells) else ""
                    outcome = str(cells[outcome_i]) if outcome_i is not None and outcome_i < len(cells) else ""
                    try:
                        fval = float(val_raw)
                    except (TypeError, ValueError):
                        continue
                    if fval <= 0:
                        continue
                    cids.append(cid)
                    parsed_rows.append((cid, act_name or "IC50", fval, outcome))
                    if len(parsed_rows) >= limit - len(records):
                        break

                if not cids:
                    continue
                # Batch resolve SMILES from CIDs (max 100 per chunk)
                smiles_map: dict[str, str] = {}
                for i in range(0, len(cids), 100):
                    chunk = ",".join(sorted(set(cids[i : i + 100])))
                    s_resp = await client.get(
                        f"{PUBCHEM_BASE}/compound/cid/{chunk}/property/IsomericSMILES,CanonicalSMILES/JSON"
                    )
                    if s_resp.status_code == 200:
                        for prop in s_resp.json().get("PropertyTable", {}).get("Properties", []):
                            smi = prop.get("IsomericSMILES") or prop.get("CanonicalSMILES") or prop.get("SMILES")
                            if smi:
                                smiles_map[str(prop["CID"])] = smi

                for cid, act_name, fval_um, outcome in parsed_rows:
                    smi = smiles_map.get(cid)
                    if not smi:
                        continue
                    norm_type = act_name.upper()
                    if "KI" in norm_type:
                        stype = "Ki"
                    elif "KD" in norm_type:
                        stype = "Kd"
                    elif "EC50" in norm_type:
                        stype = "EC50"
                    else:
                        stype = "IC50"
                    records.append(
                        BioactivityRecord(
                            compound_id=f"CID{cid}",
                            name=f"CID{cid}",
                            smiles=smi,
                            standard_type=stype,
                            standard_relation="=",
                            standard_value=fval_um,
                            standard_units="uM",
                            source="PubChem",
                            assay_id=f"AID{aid}",
                            assay_description=f"PubChem BioAssay AID{aid} ({outcome})",
                            target_name=gene_or_query,
                        ).to_dict()
                    )

            return ConnectorResult(
                source="PubChem",
                ok=True,
                records=records,
                metadata={"aids_queried": aids[:3], "count": len(records)},
            )
    except Exception as exc:
        return ConnectorResult(source="PubChem", ok=False, error=str(exc))
