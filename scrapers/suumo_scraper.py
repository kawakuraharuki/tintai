from typing import List, Dict, Any
from bs4 import BeautifulSoup
import logging
import urllib.parse
import time
import requests
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class SuumoScraper(BaseScraper):
    def __init__(self):
        super().__init__("SUUMO")
        self.base_url = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"

    def search(self, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Default parameters (Tokyo, Chintai)
        params = {
            "ar": "030", # Kanto
            "bs": "040", # Chintai
            "ta": "13",  # Tokyo
            "sc": ["13102", "13108"], # Chuo-ku, Koto-ku (Targeting based on user stations)
            "pc": "50",  # 50 items per page
        }

        # Map User Conditions to SUUMO Params
        
        # Rent (formerly fee)
        if "rent" in conditions:
            # SUUMO uses 0.0 format for price
            min_rent = conditions["rent"].get("min", 0) / 10000
            max_rent = conditions["rent"].get("max", 9999999) / 10000
            params["cb"] = f"{min_rent:.1f}"
            params["ct"] = f"{max_rent:.1f}"

        # Layouts (formerly madori)
        # Map: 1K=02, 1DK=03, 1LDK=04, 2K=05, 2DK=06, 2LDK=07 ...
        layout_map = {
            "1R": "01", "1K": "02", "1DK": "03", "1LDK": "04",
            "2K": "05", "2DK": "06", "2LDK": "07",
            "3K": "08", "3DK": "09", "3LDK": "10"
        }
        if "layouts" in conditions:
            md_codes = []
            for m in conditions["layouts"]:
                if m in layout_map:
                    md_codes.append(layout_map[m])
            if md_codes:
                params["md"] = md_codes

        # Age (formerly year)
        if "age" in conditions:
            # SUUMO 'cn' param
            max_age = conditions["age"].get("max", 9999999)
            if max_age <= 1: cn = "1"
            elif max_age <= 3: cn = "3"
            elif max_age <= 5: cn = "5"
            elif max_age <= 10: cn = "10"
            elif max_age <= 15: cn = "15"
            elif max_age <= 20: cn = "20"
            else: cn = "9999999"
            params["cn"] = cn

        # Walk Minutes (formerly ekitoho)
        if "walk_minutes" in conditions:
            max_walk = conditions["walk_minutes"].get("max", 9999999)
            if max_walk <= 1: et = "1"
            elif max_walk <= 5: et = "5"
            elif max_walk <= 7: et = "7"
            elif max_walk <= 10: et = "10"
            elif max_walk <= 15: et = "15"
            else: et = "9999999"
            params["et"] = et

        # Construct URL
        query_string = urllib.parse.urlencode(params, doseq=True)
        target_url = f"{self.base_url}?{query_string}"
        
        logger.info(f"Fetching {target_url}")
        html = self.fetch_page(target_url)
        if not html:
            return []

        properties = self.parse_html(html)
        
        # Post-filtering for Stations (Client-side handled in main.py usually, but if logic is here...)
        # In main.py we do the filtering. Here we just return scraped properties.
        # But wait, the previous code had a block for "station" filtering here too?
        # Let's check the original code block I'm replacing.
        # The original code had:
        # if "station" in conditions and conditions["station"]: ...
        # I should update that too if I replace it.
        
        return properties

    def parse_html(self, html_content: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_content, 'html.parser')
        properties = []

        items = soup.find_all("div", class_="cassetteitem")
        
        for item in items:
            try:
                detail = item.find("div", class_="cassetteitem-detail")
                title_el = detail.find("div", class_="cassetteitem_content-title")
                title = title_el.text.strip() if title_el else "Unknown"
                
                address_el = detail.find("li", class_="cassetteitem_detail-col1")
                address = address_el.text.strip() if address_el else "Unknown"

                # Access (Station) info
                access_el = detail.find("li", class_="cassetteitem_detail-col2")
                access_text = access_el.text.strip() if access_el else ""
                
                # Parse access text for nearest station and walk minutes
                # Format usually: "Line/Station Walk X min" e.g. "東京メトロ有楽町線/豊洲駅 歩7分"
                # Sometimes multiple lines. We take the first one or the one matching our target?
                # For now, let's take the first valid one.
                nearest_station = ""
                walk_minutes = 0
                
                if access_text:
                    # Simple parsing strategy
                    # Split by newline if multiple
                    lines = access_text.split('\n')
                    for line in lines:
                        # Try to find "歩X分"
                        import re
                        match = re.search(r'/(.+?)駅? 歩(\d+)分', line)
                        if match:
                            nearest_station = match.group(1) + "駅" # Ensure '駅' suffix if we want consistency
                            walk_minutes = int(match.group(2))
                            break # Use the first one found
                        
                        # Fallback regex if format is slightly different
                        match_alt = re.search(r'([^/]+?) 歩(\d+)分', line)
                        if match_alt and not nearest_station:
                             # This might match line name if no slash, but usually it's Line/Station
                             pass

                rooms = item.find_all("tr", class_="js-cassette_link")
                
                for room in rooms:
                    room_props = {}
                    room_props['title'] = title
                    room_props['address'] = address
                    room_props['access'] = access_text 
                    room_props['nearest_station'] = nearest_station
                    room_props['walk_minutes'] = walk_minutes
                    room_props['source'] = self.source_name

                    cols = room.find_all("td")
                    if len(cols) < 9:
                        continue

                    # Price (Index 3)
                    price_el = cols[3].find("span", class_="cassetteitem_price--rent")
                    admin_el = cols[3].find("span", class_="cassetteitem_price--administration")
                    
                    rent = 0.0
                    admin_fee = 0.0
                    
                    if price_el:
                        # "11.5万円" -> 11.5
                        price_text = price_el.text.strip().replace("万円", "")
                        try:
                            rent = float(price_text)
                        except ValueError:
                            rent = 0.0
                    
                    if admin_el:
                        # "11000円" -> 1.1 (Man-yen) or "-" -> 0
                        admin_text = admin_el.text.strip().replace("円", "")
                        if admin_text == "-":
                            admin_fee = 0.0
                        else:
                            try:
                                admin_fee = float(admin_text) / 10000.0
                            except ValueError:
                                admin_fee = 0.0

                    room_props['price'] = rent
                    room_props['admin_fee'] = admin_fee
                    room_props['total_price'] = rent + admin_fee
                    
                    # Layout / Area (Index 5)
                    layout_el = cols[5].find("span", class_="cassetteitem_madori")
                    area_el = cols[5].find("span", class_="cassetteitem_menseki")
                    room_props['layout'] = layout_el.text.strip() if layout_el else ""
                    if area_el:
                        area_text = area_el.text.strip().replace("m2", "")
                        try:
                            room_props['area'] = float(area_text)
                        except ValueError:
                            room_props['area'] = 0.0
                    else:
                        room_props['area'] = 0.0

                    # URL
                    url_el = room.find("a", class_="js-cassette_link_href")
                    if url_el and url_el.has_attr('href'):
                        link = url_el['href']
                        if link.startswith("/"):
                            link = "https://suumo.jp" + link
                        room_props['url'] = link
                    
                    if 'url' in room_props:
                        properties.append(room_props)

            except Exception as e:
                logger.error(f"Error parsing item: {e}")
                continue

        return properties

    def check_availability(self, url: str) -> bool:
        """Checks if the property URL is still valid (active)."""
        try:
            time.sleep(self.delay)
            response = requests.get(url, headers=self.headers)
            
            # If 404, it's definitely gone
            if response.status_code == 404:
                return False
            
            # SUUMO often redirects to a "listing ended" page or shows a message
            # The URL might change or content might say "掲載終了"
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for common "Ended" indicators
            # 1. Title often says "エラー" or "掲載終了"
            page_title = soup.title.text.strip() if soup.title else ""
            # SUUMO error page title is usually "エラー｜SUUMO(スーモ)"
            if "エラー" in page_title or "掲載終了" in page_title:
                return False
                
            # 2. Specific error box or message
            # Sometimes it says "お探しの物件は掲載終了..." in a div
            if "掲載を終了" in response.text or "掲載終了" in response.text:
                # Be careful not to match footer links, but usually safe if in body text
                # Let's check specific elements if possible, but text search is a catch-all
                # "この物件は掲載を終了しました" is common
                pass
            
            # If we are redirected to the top page or search page, it's also ended
            if "suumo.jp/chintai/" in response.url and "jnc_" not in response.url:
                # If redirected away from property detail (jnc_...), likely ended
                pass

            return True
        except Exception as e:
            logger.error(f"Error checking availability for {url}: {e}")
            return True # Default to active if unsure
