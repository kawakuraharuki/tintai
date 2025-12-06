import re
import requests
from bs4 import BeautifulSoup
import logging
import time
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from .stealth_wrapper import stealth_sync
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class AtHomeScraper(BaseScraper):
    def __init__(self):
        super().__init__("AtHome")
        self.base_url = "https://www.athome.co.jp/chintai/"

    def search(self, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        # ... (same as before) ...
        # (omitted for brevity in replacement, but I must be careful not to delete it if I use replace_file_content)
        # Actually I should target specific blocks.
        pass

    # I will do multiple replacements to be safe.
    # First, add import re at the top.
    pass

class AtHomeScraper(BaseScraper):
    def __init__(self):
        super().__init__("AtHome")
        self.base_url = "https://www.athome.co.jp/chintai/"

    def search(self, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Searches for properties on at HOME using Playwright.
        """
        # Example URL for Koto-ku
        url = "https://www.athome.co.jp/chintai/tokyo/koto-city/list/"
        
        params = []
        # Price (Rent)
        if 'rent' in conditions:
            rent_cond = conditions['rent']
            if 'min' in rent_cond and rent_cond['min'] > 0:
                params.append(f"PRMIN={rent_cond['min']}")
            if 'max' in rent_cond and rent_cond['max'] > 0:
                params.append(f"PRMAX={rent_cond['max']}")
        
        if params:
            url += "?" + "&".join(params)

        logger.info(f"Fetching {url} with Playwright...")
        properties = []
        
        try:
            with sync_playwright() as p:
                # Launch browser
                # Try Firefox
                browser = p.firefox.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                
                # Apply stealth
                stealth_sync(page)
                
                # Navigate to top page first
                logger.info("Visiting top page...")
                page.goto("https://www.athome.co.jp/", timeout=60000)
                page.wait_for_timeout(5000)
                
                # Navigate to target
                logger.info(f"Navigating to {url}...")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # Get content
                html = page.content()
                properties = self.parse_html(html)
                
                browser.close()

        except Exception as e:
            logger.error(f"Error fetching AtHome data with Playwright: {e}")

        return properties

    def parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        properties = []
        
        # Select building items
        buildings = soup.select(".p-property")
        
        logger.info(f"Found {len(buildings)} buildings in HTML")
        
        if not buildings:
             # Fallback or debug
             logger.warning("No buildings found. Saving HTML to athome_debug.html")
        
        # Always save for debugging selectors
        with open("athome_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        for building in buildings:
            try:
                # Building Title
                title_el = building.select_one("h2.p-property__title--building")
                title = title_el.text.strip() if title_el else "Unknown"
                
                # Access (Building level)
                access_text = ""
                access_el = building.select_one(".p-property__information-hint dd")
                if access_el:
                    access_text = access_el.text.strip()
                
                # Parse Station/Walk from access_text
                nearest_station = ""
                walk_minutes = 0
                if access_text:
                    # Example: "ＪＲ総武線 「亀戸」駅 徒歩4分"
                    match = re.search(r'「(.*?)」駅.*?徒歩(\d+)分', access_text)
                    if match:
                        nearest_station = match.group(1)
                        walk_minutes = int(match.group(2))
                    else:
                        match = re.search(r'(.+?)駅.*?徒歩(\d+)分', access_text)
                        if match:
                            nearest_station = match.group(1).strip()
                            walk_minutes = int(match.group(2))

                # Rooms
                rooms = building.select(".p-property__room--detail-information")
                
                if not rooms:
                     rooms = building.select("tbody tr")

                for room in rooms:
                    # Rent
                    price_el = room.select_one(".p-property__room-rent")
                    price_text = price_el.text.strip() if price_el else "0"
                    
                    rent = 0.0
                    try:
                        match = re.search(r'([\d\.]+)', price_text)
                        if match:
                            rent = float(match.group(1))
                    except:
                        pass
                        
                    # Admin Fee
                    admin_fee = 0.0
                    admin_el = room.select_one(".p-property__information-price span")
                    if not admin_el:
                        admin_el = room.select_one(".p-property__information-price")
                    
                    if admin_el:
                        admin_text = admin_el.text.strip().replace(",", "").replace("円", "").replace("管理費等", "").strip()
                        if admin_text != "-" and admin_text.isdigit():
                            try:
                                admin_fee = float(admin_text) / 10000.0
                            except:
                                pass
                    
                    total_price = rent + admin_fee
                    
                    # Layout
                    layout = ""
                    layout_el = room.select_one(".p-property__floor")
                    if layout_el:
                        layout = layout_el.text.strip()
                    
                    # Area
                    area = "0"
                    # Search for m2 in room elements
                    area_el = room.find(string=lambda t: "m²" in t if t else False)
                    if area_el:
                        area = area_el.strip().replace("m²", "")
                    
                    # URL
                    link = ""
                    url_el = room.select_one(".p-property__room-more-link a")
                    if url_el:
                        link = url_el.get('href')
                    
                    if link and not link.startswith("http"):
                        link = f"https://www.athome.co.jp{link}"

                    prop = {
                        "title": title, # Use building title
                        "price": rent,
                        "admin_fee": admin_fee,
                        "total_price": total_price,
                        "layout": layout,
                        "area": area,
                        "access": access_text,
                        "nearest_station": nearest_station,
                        "walk_minutes": walk_minutes,
                        "url": link,
                        "source": "AtHome",
                        "status": "active"
                    }
                    
                    if rent > 0 and link:
                        properties.append(prop)

            except Exception as e:
                logger.warning(f"Error parsing AtHome building: {e}")
                continue
                
        return properties

    def check_availability(self, url: str) -> bool:
        try:
            time.sleep(self.delay)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return False
            
            # Check for specific "Ended" text
            if "掲載終了" in response.text or "お探しのページは見つかりません" in response.text:
                return False
                
            return True
        except:
            return True
