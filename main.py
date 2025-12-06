import argparse
import logging
import sys
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from config import SEARCH_CONDITIONS
from csv_manager import CSVManager
from scrapers.suumo_scraper import SuumoScraper
from scrapers.homes_scraper import HomesScraper
from scrapers.athome_scraper import AtHomeScraper
from scrapers.google_maps_scraper import GoogleMapsScraper
from utils import extract_station_name

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Real Estate Search System")
    parser.add_argument("--scrape", action="store_true", help="Run scrapers to fetch new data")
    parser.add_argument("--show", action="store_true", help="Show stored properties")
    parser.add_argument("--min-price", type=float, help="Minimum price (Man-yen)")
    parser.add_argument("--max-price", type=float, help="Maximum price (Man-yen)")
    parser.add_argument("--api-key", type=str, help="Google Maps API Key", default=os.environ.get("GOOGLE_MAPS_API_KEY"))
    parser.add_argument("--force-recalc", action="store_true", help="Force recalculation of walking distance (ignore CSV cache)")
    args = parser.parse_args()

    csv_manager = CSVManager()
    
    # Initialize Google Maps Client
    # If no key provided, it will log a warning and return 0, effectively disabling it safely.
    from scrapers.google_maps_api import GoogleMapsClient
    gmaps_client = GoogleMapsClient(api_key=args.api_key)

    # Load conditions from search_conditions.json
    import json
    # import os (removed to avoid UnboundLocalError)
    conditions = SEARCH_CONDITIONS.copy()
    json_path = os.path.join(os.path.dirname(__file__), "search_conditions.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                user_conditions = json.load(f)
                conditions.update(user_conditions)
                logger.info(f"Loaded conditions from {json_path}")
        except Exception as e:
            logger.error(f"Failed to load search_conditions.json: {e}")

    if args.scrape:
        logger.info("Starting scrape...")
        scrapers = [
            SuumoScraper(),
            # HomesScraper() # Blocked by WAF
            AtHomeScraper()
        ]
        
        all_properties = []
        for scraper in scrapers:
            try:
                logger.info(f"Running {scraper.source_name} scraper with conditions: {conditions}")
                properties = scraper.search(conditions)
                
                existing_props = csv_manager.get_all_properties()
                existing_map = {p['url']: p for p in existing_props}

                # Filter by Station FIRST
                if "stations" in conditions and conditions["stations"]:
                    target_stations = conditions["stations"]
                    filtered = []
                    for p in properties:
                        access = p.get('access', '')
                        if any(station in access for station in target_stations):
                            filtered.append(p)
                    logger.info(f"Filtered {len(properties)} -> {len(filtered)} properties by station.")
                    properties = filtered

                # Then calculate walking distance for remaining properties
                for p in properties:
                    url = p.get('url')
                    # Check if we already have this property and it has walking_distance_actual
                    # SKIP this check if --force-recalc is set
                    if not args.force_recalc and url in existing_map and existing_map[url].get('walking_distance_actual'):
                        p['walking_distance_actual'] = existing_map[url]['walking_distance_actual']
                        logger.info(f"Using cached walking distance for {p['title']}")
                        continue

                    # If not, use API to get it
                    station_name = extract_station_name(p.get('access', '') or p.get('nearest_station', ''))
                    address = p.get('address')
                    title = p.get('title', '')
                    
                    if station_name and address:
                        # Clean station name (remove line name if present)
                        if "/" in station_name:
                            station_name = station_name.split("/")[1]
                        
                        # Disambiguate specific stations
                        # Kikukawa Station exists in other prefectures (e.g. Shizuoka), causing huge walking times.
                        if station_name == "菊川駅":
                            station_name = "東京都江東区 菊川駅"
                        
                        # Determine Origin: Title or Address
                        # User Rule: If title contains "{StationName}駅", it's likely a generic name -> Use Address
                        # Otherwise -> Use Title (Building Name)
                        
                        # Note: station_name usually doesn't have "駅" suffix in our extraction, 
                        # but let's check if the title has the station name followed by "駅"
                        # Actually, extract_station_name usually returns "木場" or "木場駅"? 
                        # Let's assume it returns "木場".
                        
                        check_station_str = station_name if station_name.endswith("駅") else f"{station_name}駅"
                        
                        if check_station_str in title:
                            origin = address
                            logger.info(f"Origin decision: Address (Generic title '{title}' contains '{check_station_str}')")
                        else:
                            # Use Title, but maybe append address for uniqueness? 
                            # User asked for "Building Name", but Google Maps might find a different building with same name.
                            # Let's try "Title (Address)" format or just "Title".
                            # User said "建物名から最寄り駅で検索". Let's use Title.
                            # But to be safe, let's use "Title" combined with "Address" if possible? 
                            # No, strictly follow request: "建物名から"
                            origin = title
                            logger.info(f"Origin decision: Building Name ('{title}')")

                        logger.info(f"Calculating walking distance for {p['title']} ({origin} -> {station_name})")
                        walk_minutes = gmaps_client.get_walking_time(origin, station_name)
                        if walk_minutes > 0:
                            p['walking_distance_actual'] = walk_minutes
                        else:
                            p['walking_distance_actual'] = None

                # Verify availability of each property (to catch stale search results)
                # This is slower but ensures accuracy
                verified_properties = []
                for p in properties:
                    url = p.get('url')
                    if url:
                        # We can optimize by only checking if we suspect it, but for now check all
                        # Or maybe we can check if it was previously 'ended'?
                        # But if it's in search results, it might be a new listing with same URL? Unlikely.
                        # Let's check all for now.
                        if scraper.check_availability(url):
                            verified_properties.append(p)
                        else:
                            logger.warning(f"Property in search results but ended: {p.get('title')} ({url})")
                            # We could add it as 'ended' status instead of dropping it?
                            p['status'] = 'ended'
                            verified_properties.append(p)
                    else:
                        verified_properties.append(p)
                
                all_properties.extend(verified_properties)
            except Exception as e:
                logger.error(f"Error in {scraper.source_name} scraper: {e}")

        # 1. Save new/updated properties
        if all_properties:
            logger.info(f"Saving {len(all_properties)} properties to CSV...")
            # Ensure they are marked active if not already set
            for p in all_properties:
                if "status" not in p:
                    p["status"] = "active"
            csv_manager.save_properties(all_properties)
        else:
            logger.info("No new properties found in this scrape.")

        # 2. Check for "Listing Ended" properties
        # Logic: Properties in CSV that are 'active' but NOT in all_properties (the new scrape result)
        # might be ended. We should verify them.
        
        existing_props = csv_manager.get_all_properties()
        new_urls = set(p['url'] for p in all_properties)
        
        # Candidates for checking: Active in CSV but not in New Scrape
        candidates = [p for p in existing_props if p.get('status') == 'active' and p.get('url') not in new_urls]
        
        if candidates:
            logger.info(f"Checking status of {len(candidates)} properties missing from search result...")
            # Use the scraper instance to check availability
            suumo_scraper = SuumoScraper()
            homes_scraper = HomesScraper()
            athome_scraper = AtHomeScraper()
            
            for p in candidates:
                url = p.get('url')
                source = p.get('source')
                if not url: continue
                
                scraper = None
                if source == 'SUUMO':
                    scraper = suumo_scraper
                elif source == 'Homes':
                    scraper = homes_scraper
                elif source == 'AtHome':
                    scraper = athome_scraper
                
                if not scraper:
                    logger.warning(f"No scraper found for source {source}, skipping verification for {url}")
                    continue
                
                logger.info(f"Verifying: {p.get('title')} ({url})")
                is_active = scraper.check_availability(url)
                
                if not is_active:
                    logger.info(f"-> Listing Ended. Updating status.")
                    csv_manager.update_status(url, "ended")
                else:
                    logger.info(f"-> Still Active (maybe conditions changed or rank dropped).")
                    # Optionally update timestamp to show we checked?
                    # csv_manager.update_status(url, "active") 
                    pass
        else:
            logger.info("No properties need status verification.")

    if args.show:
        properties = csv_manager.get_all_properties()
        
        # Filter in memory
        filtered_properties = []
        for p in properties:
            # CSV reads as strings/floats/ints depending on pandas inference
            # Ensure price is float
            try:
                # Use total_price if available, otherwise price
                total_price = float(p.get('total_price', 0))
                if total_price == 0:
                     total_price = float(p.get('price', 0))
            except:
                total_price = 0.0
            
            if args.min_price and total_price < args.min_price:
                continue
            if args.max_price and total_price > args.max_price:
                continue
            filtered_properties.append(p)
            
        print(f"Found {len(filtered_properties)} properties in CSV (Total: {len(properties)}):")
        for p in filtered_properties:
            price_str = f"{p.get('price')}万円"
            if p.get('admin_fee') and float(p.get('admin_fee')) > 0:
                price_str += f" + {p.get('admin_fee')}万円"
            
            status = p.get('status', 'unknown')
            status_mark = "[ENDED]" if status == "ended" else ""
            
            print(f"- {status_mark}[{p.get('source')}] {p.get('title')} ({price_str}) {p.get('layout')} {p.get('area')}m2")
            print(f"  URL: {p.get('url')}")
            print(f"  Updated: {p.get('last_updated')}")

    if not args.scrape and not args.show:
        parser.print_help()

if __name__ == "__main__":
    main()
