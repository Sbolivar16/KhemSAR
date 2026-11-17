"""Mocked integration tests for all 10 open scientific database connectors."""

import pytest
import respx
from httpx import Response

from khemsar.connectors.orchestrator import run_multidb_search


@pytest.mark.asyncio
@respx.mock
async def test_multidb_orchestrator_mocked() -> None:
    respx.get("https://rest.uniprot.org/uniprotkb/search").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "primaryAccession": "P35354",
                        "proteinDescription": {"recommendedName": {"fullName": {"value": "Prostaglandin G/H synthase 2"}}},
                        "genes": [{"geneName": {"value": "PTGS2"}}],
                        "organism": {"scientificName": "Homo sapiens"},
                        "uniProtKBCrossReferences": [{"database": "PDB", "id": "3LN1"}],
                    }
                ]
            },
        )
    )
    respx.get("https://www.ebi.ac.uk/chembl/api/data/target/search.json").mock(
        return_value=Response(
            200,
            json={
                "targets": [
                    {
                        "target_chembl_id": "CHEMBL230",
                        "pref_name": "Cyclooxygenase-2",
                        "target_type": "SINGLE PROTEIN",
                        "organism": "Homo sapiens",
                        "target_components": [{"accession": "P35354"}],
                    }
                ]
            },
        )
    )
    respx.get("https://www.ebi.ac.uk/chembl/api/data/activity.json").mock(
        return_value=Response(
            200,
            json={
                "activities": [
                    {
                        "molecule_chembl_id": "CHEMBL118",
                        "molecule_pref_name": "CELECOXIB",
                        "canonical_smiles": "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1",
                        "standard_type": "IC50",
                        "standard_relation": "=",
                        "standard_value": "40.0",
                        "standard_units": "nM",
                        "document_year": 1997,
                        "assay_chembl_id": "CHEMBL661",
                        "confidence_score": 9,
                    }
                ],
                "page_meta": {"next": None},
            },
        )
    )
    respx.get("https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/genesymbol/PTGS2/aids/JSON").mock(
        return_value=Response(200, json={"InformationList": {"Information": [{"AID": [1234]}]}})
    )
    respx.get("https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/aid/1234/concise/JSON").mock(
        return_value=Response(
            200,
            json={
                "Table": {
                    "Columns": {"Column": ["CID", "Activity Name", "Activity Value [uM]", "Activity Outcome"]},
                    "Row": [{"Cell": ["2662", "IC50", "0.04", "Active"]}],
                }
            },
        )
    )
    respx.get("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2662/property/IsomericSMILES,CanonicalSMILES/JSON").mock(
        return_value=Response(
            200,
            json={"PropertyTable": {"Properties": [{"CID": 2662, "CanonicalSMILES": "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1"}]}},
        )
    )
    respx.get("https://bindingdb.org/rest/getLigandsByUniprot").mock(
        return_value=Response(
            200,
            json={"getLigandsByUniprotResponse": {"affinities": [{"monomerid": "5001", "smile": "CS(=O)(=O)c1ccc(C2=C(c3ccccc3)C(=O)OC2)cc1", "affinity": "18.0", "affinity_type": "IC50"}]}},
        )
    )
    respx.get("https://www.guidetopharmacology.org/services/targets").mock(
        return_value=Response(200, json=[{"targetId": 1376, "name": "COX-2"}])
    )
    respx.get("https://www.guidetopharmacology.org/services/targets/1376/interactions").mock(
        return_value=Response(200, json=[{"ligandId": 2713, "affinityMedian": 7.5, "affinityType": "pIC50", "action": "Inhibition"}])
    )
    respx.get("https://www.guidetopharmacology.org/services/ligands/2713").mock(
        return_value=Response(200, json={"name": "Rofecoxib", "smiles": "CS(=O)(=O)c1ccc(C2=C(c3ccccc3)C(=O)OC2)cc1"})
    )
    respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(
        return_value=Response(200, json={"result_set": [{"identifier": "3LN1", "score": 1.0}]})
    )
    respx.get("https://data.rcsb.org/rest/v1/core/entry/3LN1").mock(
        return_value=Response(200, json={"struct": {"title": "COX-2 with Celecoxib"}, "rcsb_entry_info": {"resolution_combined": [2.4]}, "exptl": [{"method": "X-RAY DIFFRACTION"}]})
    )
    respx.get("https://alphafold.ebi.ac.uk/api/prediction/P35354").mock(
        return_value=Response(200, json=[{"entryId": "AF-P35354-F1", "uniprotAccession": "P35354", "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P35354-F1-model_v4.pdb"}])
    )
    respx.post("https://api.platform.opentargets.org/api/v4/graphql").mock(
        side_effect=[
            Response(200, json={"data": {"search": {"hits": [{"id": "ENSG00000073756"}]}}}),
            Response(200, json={"data": {"target": {"id": "ENSG00000073756", "approvedSymbol": "PTGS2", "approvedName": "Prostaglandin-endoperoxide synthase 2", "tractability": [], "associatedDiseases": {"rows": []}, "knownDrugs": {"rows": []}}}}),
        ]
    )
    respx.get("https://coconut.naturalproducts.net/api/search/simple").mock(
        return_value=Response(200, json={"data": [{"identifier": "CNP001", "name": "Curcumin", "canonical_smiles": "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O"}]})
    )

    res = await run_multidb_search("PTGS2", max_records=100)
    assert res["resolved_target"]["chembl_target_id"] == "CHEMBL230"
    assert res["resolved_target"]["uniprot_id"] == "P35354"
    assert len(res["bioactivities"]) == 4  # ChEMBL + PubChem + BindingDB + GtoPdb
    assert res["pdb_structures"][0]["pdb_id"] == "3LN1"
    assert len(res["alphafold"]) == 1
    assert len(res["opentargets"]) == 1
    assert len(res["coconut_natural_products"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_pdb_only_search_resolves_without_500() -> None:
    respx.get("https://data.rcsb.org/rest/v1/core/entry/2FOM").mock(
        return_value=Response(200, json={"struct": {"title": "Crystal structure of Dengue Virus NS2B-NS3 protease"}})
    )
    respx.get("https://data.rcsb.org/rest/v1/core/polymer_entity/2FOM/1").mock(
        return_value=Response(
            200,
            json={
                "rcsb_polymer_entity": {"pdbx_description": "NS3 protease"},
                "rcsb_polymer_entity_container_identifiers": {"uniprot_ids": ["P29990"]},
            },
        )
    )
    respx.get("https://rest.uniprot.org/uniprotkb/search").mock(return_value=Response(500))
    respx.get("https://www.ebi.ac.uk/chembl/api/data/target.json").mock(return_value=Response(404))
    respx.get("https://www.ebi.ac.uk/chembl/api/data/target/search.json").mock(return_value=Response(500))
    respx.get("https://pubchem.ncbi.nlm.nih.gov/rest/pug/assay/target/genesymbol/NS3%20protease/aids/JSON").mock(return_value=Response(404))
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(return_value=Response(200, json={"esearchresult": {"idlist": []}}))
    respx.get("https://bindingdb.org/rest/getLigandsByUniprot").mock(
        return_value=Response(
            200,
            json={"getLigandsByUniprotResponse": {"affinities": [{"monomerid": "101", "smile": "c1ccccc1C(=O)O", "affinity": "250", "affinity_type": "IC50"}]}},
        )
    )
    respx.get("https://www.guidetopharmacology.org/services/targets").mock(return_value=Response(200, json=[]))
    respx.post("https://search.rcsb.org/rcsbsearch/v2/query").mock(return_value=Response(200, json={"result_set": [{"identifier": "2FOM"}]}))
    respx.get("https://alphafold.ebi.ac.uk/api/prediction/P29990").mock(return_value=Response(404))
    respx.post("https://api.platform.opentargets.org/api/v4/graphql").mock(return_value=Response(404))
    respx.get("https://coconut.naturalproducts.net/api/search/simple").mock(return_value=Response(404))

    res = await run_multidb_search(target_query="", pdb_id="2FOM")
    assert res["query"] == "NS3 protease"
    assert res["resolved_target"]["uniprot_id"] == "P29990"
    assert len(res["bioactivities"]) == 1
    assert res["pdb_structures"][0]["pdb_id"] == "2FOM"
