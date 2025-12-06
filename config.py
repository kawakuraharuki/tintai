import os

# Database configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "properties.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Scraping configuration
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT
}
REQUEST_DELAY = 0.5  # Seconds to wait between requests

# Search configuration (Example)
SEARCH_CONDITIONS = {
    "min_price": 50000,
    "max_price": 150000,
    "areas": ["Tokyo", "Kanagawa"]
}
