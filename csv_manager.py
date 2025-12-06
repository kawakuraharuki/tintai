import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CSVManager:
    def __init__(self, file_path="properties.csv"):
        self.file_path = file_path
        # Reordered columns as requested
        self.columns = [
            "status", "title", "total_price", "price", "admin_fee", 
            "layout", "area", "nearest_station", "walk_minutes", "walking_distance_actual", "address", "access", "url", "last_updated", "source"
        ]

    def save_properties(self, properties_data: List[Dict[str, Any]]):
        # Convert new data to DataFrame
        new_df = pd.DataFrame(properties_data)
        if new_df.empty:
            # If no new data, we might still be updating statuses of existing data passed in
            pass

        # Add/Update timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not new_df.empty:
            new_df["last_updated"] = current_time
            if "status" not in new_df.columns:
                new_df["status"] = "active" # Default for new scrapes
        
        # Ensure all columns exist
        for col in self.columns:
            if col not in new_df.columns:
                new_df[col] = None
        
        # Select and order columns
        new_df = new_df[self.columns]

        if os.path.exists(self.file_path):
            try:
                existing_df = pd.read_csv(self.file_path)
                
                # Ensure existing DF has all columns (for migration)
                for col in self.columns:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                        if col == "status":
                            existing_df["status"] = "active" # Assume active if missing

                # Merge logic:
                # 1. Set index to URL for easy update
                existing_df.set_index("url", inplace=True)
                new_df.set_index("url", inplace=True)
                
                # 2. Update existing with new data
                # combine_first prefers the caller (existing_df) if not null, so we use update or manual
                # We want new_df to overwrite existing_df for overlapping rows
                existing_df.update(new_df)
                
                # 3. Append new rows that are not in existing
                new_rows = new_df[~new_df.index.isin(existing_df.index)]
                combined_df = pd.concat([existing_df, new_rows])
                
                # Reset index
                combined_df.reset_index(inplace=True)
                
                # Reorder columns
                combined_df = combined_df[self.columns]
                
                combined_df.to_csv(self.file_path, index=False, encoding="utf-8-sig")
                logger.info(f"Updated CSV. Total properties: {len(combined_df)}")
            except Exception as e:
                logger.error(f"Error updating CSV: {e}")
                raise
        else:
            new_df.to_csv(self.file_path, index=False, encoding="utf-8-sig")
            logger.info(f"Created new CSV with {len(new_df)} properties.")

    def update_status(self, url: str, status: str):
        """Updates the status of a specific property."""
        if not os.path.exists(self.file_path):
            return
        
        try:
            df = pd.read_csv(self.file_path)
            if "url" in df.columns:
                mask = df["url"] == url
                if mask.any():
                    df.loc[mask, "status"] = status
                    df.loc[mask, "last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.to_csv(self.file_path, index=False, encoding="utf-8-sig")
                    logger.info(f"Updated status for {url} to {status}")
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def get_all_properties(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            return []
        try:
            df = pd.read_csv(self.file_path)
            # Replace NaN with None for valid JSON serialization
            # Must cast to object first to allow None in float columns
            df = df.astype(object).where(pd.notnull(df), None)
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return []
