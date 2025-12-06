import logging
import time
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .stealth_wrapper import stealth_sync
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class HomesScraper(BaseScraper):
    def __init__(self):
        super().__init__("Homes")
        self.base_url = "https://www.homes.co.jp/chintai/"

    def search(self, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Searches for properties on LIFULL HOME'S using Playwright.
        """
        # Example URL for Koto-ku
        url = "https://www.homes.co.jp/chintai/tokyo/koto-city/list/"
        
        logger.info(f"Fetching {url} with Playwright...")
        properties = []
        
        try:
            with sync_playwright() as p:
                # Launch browser
                # Use headless=True but with args to mimic real browser
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                
                # Apply stealth
                stealth_sync(page)
                
                # Navigate to top page first to behave like a human
                logger.info("Visiting top page...")
                page.goto("https://www.homes.co.jp/", timeout=60000)
                page.wait_for_timeout(3000) # Wait 3 seconds
                
                # Then navigate to target
                logger.info(f"Navigating to {url}...")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # Get content
                html = page.content()
                properties = self.parse_html(html)
                
                browser.close()
                
        except Exception as e:
            logger.error(f"Error fetching Homes data with Playwright: {e}")

        return properties

    def parse_html(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        properties = []
        
        # Select property items
        # Try multiple selectors as HOME'S might change or have different layouts
        items = soup.select(".ui-frame") 
        if not items:
            items = soup.select(".moduleArticleList")
        if not items:
            items = soup.select(".prg-bukkenList .ui-frame")
            
        logger.info(f"Found {len(items)} items in HTML")
        
        if not items:
            with open("homes_debug_pw.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Saved HTML to homes_debug_pw.html for debugging")
            
        for item in items:
            try:
                # Title
                title_el = item.select_one(".bukkenName")
                title = title_el.text.strip() if title_el else "Unknown"
                
                # Price
                price_el = item.select_one(".price")
                price_text = price_el.text.strip() if price_el else "0"
                # Parse "11.5万円"
                rent = 0.0
                try:
                    rent = float(price_text.replace("万円", ""))
                except:
                    pass
                
                # Admin Fee
                admin_el = item.select_one(".priceAdmin")
                admin_fee = 0.0
                if admin_el:
                    admin_text = admin_el.text.strip().replace("円", "").replace("管理費等", "").strip()
                    if admin_text != "-":
                        try:
                            admin_fee = float(admin_text) / 10000.0
                        except:
                            pass
                
                total_price = rent + admin_fee

                # Layout / Area
                # These might be in a table or specific classes
                layout = ""
                area = ""
                
                # Layout often in .madori
                layout_el = item.select_one(".madori")
                if layout_el:
                    layout = layout_el.text.strip()
                
                # Area often in .menseki
                area_el = item.select_one(".menseki")
                if area_el:
                    area = area_el.text.strip().replace("m²", "")
                
                # Station / Access
                access_text = ""
                access_el = item.select_one(".traffic")
                if access_el:
                    access_text = access_el.text.strip()
                
                # URL
                link = ""
                url_el = item.select_one("a.bukkenName")
                if url_el:
                    link = url_el.get('href')
                else:
                    # Try finding any link in the item
                    link_el = item.select_one("a")
                    if link_el:
                        link = link_el.get('href')
                        
                if link and not link.startswith("http"):
                    link = f"https://www.homes.co.jp{link}"

                prop = {
                    "title": title,
                    "price": rent,
                    "admin_fee": admin_fee,
                    "total_price": total_price,
                    "layout": layout,
                    "area": area,
                    "access": access_text,
                    "url": link,
                    "source": "Homes",
                    "status": "active"
                }
                
                # Basic validation
                if title != "Unknown" and link:
                    properties.append(prop)
                    
            except Exception as e:
                logger.warning(f"Error parsing Homes item: {e}")
                continue
                
        return properties

    def check_availability(self, url: str) -> bool:
        try:
            # For availability check, we also need playwright if requests is blocked
            # But launching browser for every check is slow.
            # Maybe try requests first, if 403, assume active? Or use playwright?
            # Let's try requests with headers first.
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            time.sleep(self.delay)
            response = requests.get(url, headers=headers)
            
            if response.status_code == 404:
                return False
            if response.status_code == 403:
                # If blocked, we can't be sure. Assume active to be safe?
                # Or try playwright?
                return True 
            
            if "掲載終了" in response.text or "エラー" in response.text:
                return False
                
            return True
        except:
            return True
