"""Open Targets Platform GraphQL API connector for target-disease evidence & tractability."""

from __future__ import annotations

from typing import Any

from khemsar.connectors.base import ConnectorResult, build_async_client

OPENTARGETS_GQL = "https://api.platform.opentargets.org/api/v4/graphql"


async def fetch_opentargets_evidence(query: str) -> ConnectorResult:
    search_q = """
    query SearchTarget($q: String!) {
      search(queryString: $q, entityNames: ["target"], page: {index: 0, size: 3}) {
        hits { id name entity description }
      }
    }
    """
    detail_q = """
    query TargetDetail($ensemblId: String!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        approvedName
        tractability { label modality value }
        associatedDiseases(page: {index: 0, size: 5}) {
          rows { score disease { id name } }
        }
        knownDrugs(size: 10) {
          rows {
            drugId
            prefName
            phase
            mechanismOfAction
            drug { maximumClinicalTrialPhase }
          }
        }
      }
    }
    """
    try:
        async with build_async_client() as client:
            r1 = await client.post(OPENTARGETS_GQL, json={"query": search_q, "variables": {"q": query}})
            if r1.status_code != 200:
                return ConnectorResult(source="Open Targets", ok=False, error=f"HTTP {r1.status_code}")
            hits = r1.json().get("data", {}).get("search", {}).get("hits", [])
            if not hits:
                return ConnectorResult(source="Open Targets", ok=True, records=[])
            ensembl_id = hits[0]["id"]
            r2 = await client.post(OPENTARGETS_GQL, json={"query": detail_q, "variables": {"ensemblId": ensembl_id}})
            if r2.status_code != 200:
                return ConnectorResult(source="Open Targets", ok=False, error=f"HTTP {r2.status_code}")
            target = r2.json().get("data", {}).get("target") or {}
            diseases = [
                {"disease": row["disease"]["name"], "score": round(row["score"], 3)}
                for row in (target.get("associatedDiseases") or {}).get("rows", [])
            ]
            drugs = [
                {
                    "drug_id": row.get("drugId"),
                    "name": row.get("prefName"),
                    "phase": row.get("phase"),
                    "moa": row.get("mechanismOfAction"),
                }
                for row in (target.get("knownDrugs") or {}).get("rows", [])
            ]
            tractability = [
                t for t in (target.get("tractability") or []) if t.get("value") is True
            ]
            summary: dict[str, Any] = {
                "ensembl_id": target.get("id", ensembl_id),
                "approved_symbol": target.get("approvedSymbol", ""),
                "approved_name": target.get("approvedName", ""),
                "top_diseases": diseases,
                "known_drugs": drugs,
                "tractability": tractability,
            }
            return ConnectorResult(source="Open Targets", ok=True, records=[summary])
    except Exception as exc:
        return ConnectorResult(source="Open Targets", ok=False, error=str(exc))
