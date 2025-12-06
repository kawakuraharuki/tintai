import googlemaps
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class GoogleMapsClient:
    def __init__(self, api_key: str, cache_file: str = "route_cache.json"):
        self.api_key = api_key
        self.client = None
        if api_key:
            try:
                self.client = googlemaps.Client(key=api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google Maps API client: {e}")
        
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load route cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save route cache: {e}")

    def get_walking_time(self, origin: str, destination: str) -> int:
        """
        Get walking time in minutes from origin to destination.
        Uses cache to minimize API calls.
        """
        if not origin or not destination:
            return 0

        # Normalize keys
        key = f"{origin}|{destination}"
        
        # Check cache
        if key in self.cache:
            logger.info(f"Cache hit for {origin} -> {destination}: {self.cache[key]} min")
            return self.cache[key]

        if not self.client:
            logger.warning("Google Maps API client not initialized (no key provided).")
            return 0

        # Call API
        try:
            logger.info(f"Calling Google Maps API: {origin} -> {destination}")
            # Request directions
            # mode="walking"
            now = datetime.now()
            directions_result = self.client.directions(
                origin,
                destination,
                mode="walking",
                departure_time=now
            )

            if directions_result:
                # Extract duration
                legs = directions_result[0].get("legs", [])
                if legs:
                    duration_sec = legs[0].get("duration", {}).get("value", 0)
                    duration_min = round(duration_sec / 60)
                    
                    # Update cache
                    self.cache[key] = duration_min
                    self._save_cache()
                    
                    logger.info(f"API Result: {duration_min} min")
                    return duration_min
            
            logger.warning(f"No route found for {origin} -> {destination}")
            # Cache failure as 0 or None? 
            # If we cache 0, we won't retry. Maybe that's good to save quota?
            # Let's cache 0 for now to avoid repeated failures on bad addresses.
            self.cache[key] = 0
            self._save_cache()
            return 0

        except Exception as e:
            logger.error(f"Google Maps API error: {e}")
            return 0
