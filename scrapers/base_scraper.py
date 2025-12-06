from abc import ABC, abstractmethod
import requests
import time
import logging
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.headers = config.REQUEST_HEADERS
        self.delay = config.REQUEST_DELAY

    def fetch_page(self, url: str) -> str:
        """Fetches a single page content."""
        try:
            time.sleep(self.delay)
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""

    @abstractmethod
    def search(self, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Executes search based on conditions and returns a list of property dictionaries.
        Expected dictionary keys: title, price, address, layout, area, url
        """
        pass

    @abstractmethod
    def parse_html(self, html_content: str) -> List[Dict[str, Any]]:
        """Parses HTML content to extract property details."""
        pass
