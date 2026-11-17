"""Shared HTTP client utilities and normalized schemas for scientific database connectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

USER_AGENT = "KhemSAR/1.0 (https://github.com/Sbolivar16/KhemSAR)"


@dataclass
class BioactivityRecord:
    compound_id: str
    name: str
    smiles: str
    standard_type: str
    standard_relation: str
    standard_value: float | None
    standard_units: str
    year: int | None = None
    source: str = ""
    assay_id: str = ""
    assay_description: str = ""
    confidence_score: int | None = None
    target_name: str = ""
    target_chembl_id: str = ""
    uniprot_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectorResult:
    source: str
    ok: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_async_client(timeout: float = 25.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )
