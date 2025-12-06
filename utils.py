import re

def extract_station_name(access_text: str) -> str:
    """
    Extract station name from access string.
    Example: "東京メトロ東西線/木場駅 歩5分" -> "木場駅"
    """
    if not access_text:
        return ""
    
    # Try to find "XX駅"
    # Often formatted as "LineName/StationName WalkXmin" or "StationName WalkXmin"
    
    # Pattern 1: "「Station」駅" (AtHome style)
    match = re.search(r'「(.*?)」駅', access_text)
    if match:
        return match.group(1) + "駅"

    # Pattern 2: "Station駅"
    match = re.search(r'(\S+?駅)', access_text)
    if match:
        # Clean up if it contains slash
        station = match.group(1)
        if "/" in station:
            station = station.split("/")[-1]
        return station
        
    return ""
