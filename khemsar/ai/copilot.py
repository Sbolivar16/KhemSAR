"""AI Research Copilot: parses natural-language target & assay descriptions into multi-DB queries."""

from __future__ import annotations

import json
import re
from typing import Any

from khemsar.ai.providers import generate_llm_response
from khemsar.core.config import AISettings

COMMON_TARGET_ALIASES = {
    "cox-2": "PTGS2",
    "cox2": "PTGS2",
    "cyclooxygenase-2": "PTGS2",
    "ciclooxigenasa 2": "PTGS2",
    "egfr": "EGFR",
    "ache": "ACHE",
    "acetylcholinesterase": "ACHE",
    "acetilcolinesterasa": "ACHE",
    "bace1": "BACE1",
    "bace-1": "BACE1",
    "jak2": "JAK2",
    "hsp90": "HSP90AA1",
    "mpro": "SARS-CoV-2 3CLpro",
    "3clpro": "SARS-CoV-2 3CLpro",
    "hdac1": "HDAC1",
    "vegfr2": "KDR",
    "pparg": "PPARG",
    "ace2": "ACE2",
    "mao-b": "MAOB",
    "maob": "MAOB",
}


async def parse_research_intent(description: str, ai_settings: AISettings) -> dict[str, Any]:
    """Convert free-text medicinal chemistry goal into structured target, assay, PDB & endpoint filters."""
    text = (description or "").strip()
    if not text:
        return {
            "target_query": "PTGS2",
            "pdb_id": "",
            "standard_types": ["IC50", "Ki"],
            "task_type": "regression",
            "activity_cutoff_pAct": 6.0,
            "rationale": "Default COX-2 / PTGS2 configuration.",
            "provider": "offline",
        }

    # Try configured LLM first for nuanced extraction
    sys_prompt = (
        "Extract a structured cheminformatics search query from the user's drug-discovery goal. "
        "Respond ONLY with valid JSON containing keys: target_query (gene symbol or protein name), "
        "pdb_id (4-char PDB code if mentioned else empty string), standard_types (subset of ['IC50','Ki','Kd','EC50']), "
        "task_type ('regression' or 'classification'), activity_cutoff_pAct (float, e.g. 6.0 for 1 uM, 7.0 for 100 nM), "
        "and rationale (brief string)."
    )
    llm_raw, used_provider = await generate_llm_response(sys_prompt, text, ai_settings, temperature=0.0)
    if llm_raw:
        match = re.search(r"\{.*\}", llm_raw, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                parsed["provider"] = used_provider
                return parsed
            except Exception:
                pass

    # Deterministic medicinal-chemistry NLP fallback
    low = text.lower()
    target_query = ""
    for alias, symbol in COMMON_TARGET_ALIASES.items():
        if alias in low:
            target_query = symbol
            break

    pdb_match = re.search(r"\bpdb[:\s#-]*([0-9][a-z0-9]{3})\b", low)
    pdb_id = pdb_match.group(1).upper() if pdb_match else ""

    chembl_match = re.search(r"\b(chembl\d+)\b", low)
    chembl_id = chembl_match.group(1).upper() if chembl_match else ""

    if not target_query:
        # Strip Spanish/English/Portuguese filler words to isolate target phrase
        cleaned = re.sub(
            r"\b(busco|quiero|estudiar|inhibidores|ligandos|de|para|sobre|en|con|ensayo|diana|target|looking|for|inhibitors|of|study|active|potencia|ic50|ki|kd|ec50|pdb|nm|um)\b",
            " ",
            low,
        )
        tokens = [tok for tok in re.split(r"[^a-z0-9-]+", cleaned) if len(tok) >= 2]
        target_query = " ".join(tokens[:3]).upper() if tokens else text[:50]

    st_types: list[str] = []
    for ep in ("IC50", "Ki", "Kd", "EC50"):
        if ep.lower() in low:
            st_types.append(ep)
    if not st_types:
        st_types = ["IC50", "Ki"]

    cutoff_pact = 6.0
    nm_match = re.search(r"(\d+(?:\.\d+)?)\s*nm\b", low)
    um_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:um|µm)\b", low)
    if nm_match:
        import math

        val_nm = max(1e-3, float(nm_match.group(1)))
        cutoff_pact = round(-math.log10(val_nm * 1e-9), 2)
    elif um_match:
        import math

        val_um = max(1e-3, float(um_match.group(1)))
        cutoff_pact = round(-math.log10(val_um * 1e-6), 2)

    task_type = "classification" if any(w in low for w in ("clasific", "classif", "activo/inactivo", "active/inactive")) else "regression"

    return {
        "target_query": target_query,
        "chembl_target_id": chembl_id,
        "pdb_id": pdb_id,
        "standard_types": st_types,
        "task_type": task_type,
        "activity_cutoff_pAct": cutoff_pact,
        "rationale": f"Parsed target='{target_query}', endpoints={st_types}, cutoff pAct={cutoff_pact}.",
        "provider": "offline_nlp",
    }
