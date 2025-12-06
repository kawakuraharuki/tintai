import logging
import re
import urllib.parse
from playwright.sync_api import sync_playwright
from .stealth_wrapper import stealth_sync

logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    def __init__(self):
        self.base_url = "https://www.google.co.jp/maps/dir/"

    def get_walking_time(self, origin: str, destination: str) -> int:
        """
        Get walking time in minutes from origin to destination using Google Maps.
        Returns 0 if failed.
        """
        try:
            with sync_playwright() as p:
                # Launch browser (headless=True for background execution)
                # Try Firefox as it might be less detected or handle rendering differently
                browser = p.firefox.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
                    viewport={"width": 1920, "height": 1080},
                    locale="ja-JP"
                )
                page = context.new_page()
                stealth_sync(page)

                # Encode addresses
                origin_enc = urllib.parse.quote(origin)
                dest_enc = urllib.parse.quote(destination)
                
                # Construct URL for walking directions
                url = f"{self.base_url}{origin_enc}/{dest_enc}/data=!4m2!4m1!3e2"
                
                logger.info(f"Navigating to Google Maps: {origin} -> {destination}")
                page.goto(url, timeout=60000)
                
                # Wait for network idle to ensure page load
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass

                # Check for consent button (if any)
                try:
                    page.get_by_role("button", name="すべて同意").click(timeout=2000)
                except:
                    pass
                
                logger.info(f"Page Title: {page.title()}")
                # logger.info(f"Body text snippet: {page.inner_text('body')[:200]}")

                # Wait for the time element to appear
                # The selector for the primary travel time usually contains "分"
                # We look for the main route time display
                try:
                    # Common selectors for time in Google Maps (subject to change)
                    # Try to find the element that contains "分" and is a large text
                    # Try to find the element that contains "分"
                    # Google Maps often displays time like "12 分"
                    # We will look for all elements matching the pattern and pick the most likely one
                    # Usually the main route time is a large text
                    
                    # Wait a bit for dynamic content
                    page.wait_for_timeout(5000)
                    
                    # Get full HTML content
                    html_content = page.content()
                    
                    # Search for the pattern [seconds, "X 分"] or [seconds, "X 時間 Y 分"]
                    # This pattern appears in the embedded JSON data for route estimates
                    # Example: [900,"15 分"]
                    
                    # Regex for "X 分"
                    matches = re.findall(r'\[\d+,"(\d+)\s*分"\]', html_content)
                    found_minutes = []
                    for m in matches:
                        found_minutes.append(int(m))
                        
                    # Regex for "X 時間 Y 分"
                    # Example: [3900,"1 時間 5 分"]
                    matches_hr = re.findall(r'\[\d+,"(\d+)\s*時間\s*(\d+)\s*分"\]', html_content)
                    for h, m in matches_hr:
                        found_minutes.append(int(h) * 60 + int(m))
                        
                    # Regex for "X 時間"
                    matches_hr_only = re.findall(r'\[\d+,"(\d+)\s*時間"\]', html_content)
                    for h in matches_hr_only:
                        found_minutes.append(int(h) * 60)

                    if found_minutes:
                        # Heuristic to filter out "Schedule Explorer" options (e.g. 15, 30, 45, 60...)
                        # If we have many values and they are all multiples of 15, it's suspicious.
                        # Also if the list looks like [15, 30, 15, 30...]
                        
                        # Check if values are mostly multiples of 15
                        multiples_of_15 = [m for m in found_minutes if m % 15 == 0]
                        if len(found_minutes) >= 3 and len(multiples_of_15) == len(found_minutes):
                            logger.warning(f"Suspicious time pattern found (likely schedule options): {found_minutes}. Ignoring.")
                            return 0
                            
                        # Take the minimum time found (optimistic)
                        min_minutes = min(found_minutes)
                        logger.info(f"Found walking times: {found_minutes}. Using minimum: {min_minutes} min")
                        return min_minutes

                    logger.warning("No time pattern found in HTML content")
                    # with open("gmaps_body.html", "w") as f:
                    #     f.write(html_content)
                except Exception as e:
                    logger.warning(f"Could not find time element: {e}")
                    # Save screenshot for debugging
                    page.screenshot(path="gmaps_debug.png")
                    with open("gmaps_debug.html", "w") as f:
                        f.write(page.content())
                
                browser.close()
        except Exception as e:
            logger.error(f"Error scraping Google Maps: {e}")
        
        return 0

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    scraper = GoogleMapsScraper()
    time = scraper.get_walking_time("東京都江東区東陽３", "木場駅")
    print(f"Result: {time} min")
