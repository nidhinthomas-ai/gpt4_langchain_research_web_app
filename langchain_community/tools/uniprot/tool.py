from typing import Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.pydantic_v1 import Field
from langchain_core.tools import BaseTool

from langchain_community.utilities.uniprot import UniProtAPIWrapper

class UniprotQueryRun(BaseTool):
    """Tool that searches the UniProt API."""

    name: str = "uniprot_query"
    description: str = (
        "A wrapper around UniProt. "
        "Useful for retrieving information about proteins from the UniProt database. "
        "Input should be a search query."
    )
    api_wrapper: UniProtAPIWrapper = Field(default_factory=UniProtAPIWrapper)

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the UniProt tool."""
        return self.api_wrapper.run(query)