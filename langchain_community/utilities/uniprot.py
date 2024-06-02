import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List

from langchain_core.documents import Document
from langchain_core.pydantic_v1 import BaseModel, root_validator

logger = logging.getLogger(__name__)

class UniProtAPIWrapper(BaseModel):
    parse: Any  #: :meta private:

    base_url_search: str = "https://rest.uniprot.org/uniprotkb/search?"
    base_url_entry: str = "https://rest.uniprot.org/uniprotkb/"
    max_retry: int = 10
    sleep_time: float = 0.2

    top_k_results: int = 3
    MAX_QUERY_LENGTH: int = 300
    doc_content_chars_max: int = 10000
    email: str = "your_email@example.com"

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        return values

    def run(self, query: str) -> str:
        try:
            docs = [
                f"Entry ID: {result['Primary Accession']}\n"
                f"Protein: {result['Protein Name']}\n"
                f"Organism: {result['Organism']}\n"
                f"Function:\n{result['Function']}\n"
                f"Subcellular Location:\n{result['Subcellular Location']}\n"
                f"Domains:\n{result['Domains']}\n"
                f"Sequence:\n{result['Sequence']}\n"
                f"Structures:\n{json.dumps(result['Structures'], indent=2)}\n"
                f"PubMed Citations:\n{json.dumps(result['PubMed Citations'], indent=2)}"
                for result in self.search_proteins(query[:self.MAX_QUERY_LENGTH])
            ]
            return (
                "\n\n".join(docs)[:self.doc_content_chars_max]
                if docs
                else "No good UniProt Result was found"
            )
        except Exception as ex:
            return f"UniProt exception: {ex}"

    def search_proteins(self, query: str) -> List[Dict]:
        url = (
            self.base_url_search
            + "query="
            + urllib.parse.quote(query)
            + f"&size={self.top_k_results}"
        )
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode("utf-8"))
        results = data.get("results", [])
        return [self.get_protein_details(entry["primaryAccession"]) for entry in results]

    def get_protein_details(self, accession: str) -> Dict:
        url = self.base_url_entry + accession
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode("utf-8"))
        return self.parse_protein_details(data)

    def parse_protein_details(self, data: Dict) -> Dict:
        protein_info = data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "")
        organism_info = data.get("organism", {}).get("scientificName", "")
        function_info = data.get("comments", [])
        sequence_info = data.get("sequence", {}).get("value", "")
        references_info = data.get("references", [])
        structure_info = [ref for ref in data.get("uniProtKBCrossReferences", []) if ref.get("database") == "PDB"]

        functions = [
            comment.get('texts', [{}])[0].get('value', 'N/A')
            for comment in function_info
            if comment.get("commentType") == "FUNCTION"
        ]
        function_summary = "\n".join(functions) if functions else "No function available"

        subcellular_locations = [
            loc.get('location', {}).get('value', 'N/A')
            for comment in function_info
            if comment.get("commentType") == "SUBCELLULAR LOCATION"
            for loc in comment.get('subcellularLocations', [])
        ]
        subcellular_location_summary = "\n".join(subcellular_locations) if subcellular_locations else "No subcellular location available"

        domains = [
            comment.get('texts', [{}])[0].get('value', 'N/A')
            for comment in function_info
            if comment.get("commentType") == "DOMAIN"
        ]
        domain_summary = "\n".join(domains) if domains else "No domain information available"

        pubmed_citations = [
            {
                "title": ref.get('citation', {}).get('title', 'N/A'),
                "authors": ", ".join(ref.get('citation', {}).get('authors', [])),
                "journal": ref.get('citation', {}).get('journal', 'N/A'),
                "pubmed_id": next((cr.get('id') for cr in ref.get('citation', {}).get('citationCrossReferences', []) if cr.get('database') == 'PubMed'), 'N/A'),
                "doi": next((cr.get('id') for cr in ref.get('citation', {}).get('citationCrossReferences', []) if cr.get('database') == 'DOI'), 'N/A')
            }
            for ref in references_info
        ]

        entry = {
            "Primary Accession": data.get("primaryAccession", ""),
            "UniProtKB ID": data.get("uniProtkbId", ""),
            "Protein Name": protein_info,
            "Organism": organism_info,
            "Function": function_summary,
            "Subcellular Location": subcellular_location_summary,
            "Domains": domain_summary,
            "Sequence": sequence_info,
            "Structures": structure_info,
            "PubMed Citations": pubmed_citations
        }

        return entry