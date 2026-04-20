from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

class ContractParser:
    """
    Parses full contract HTML documents (Exhibit 10).
    """
    def __init__(self, html_content: str):
        self.soup = BeautifulSoup(html_content, 'lxml')
        self.text_content = self.soup.get_text(" ", strip=True)

    def get_clean_text(self) -> str:
        """
        Returns cleaned text content of the contract.
        """
        # Basic cleaning already done by get_text, but we can add more if needed.
        # For now, just return the text.
        return self.text_content

    def get_title(self) -> str:
        """
        Attempts to extract the contract title from the first few lines.
        """
        # Heuristic: Take the first non-empty line or first 100 chars
        lines = self.text_content.split('\n')
        for line in lines[:5]:
            clean_line = line.strip()
            if len(clean_line) > 5:
                return clean_line
        return "Unknown Contract"
