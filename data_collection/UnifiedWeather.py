import requests
import csv
import time
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
START_DATE = "2024-01-01 00:00:00"
END_DATE   = "2024-01-02 00:00:00"  # Adjust this to cover your full period
INTERVAL_MIN = 30                 # CHANGED: Synced with carpark data
OUTPUT_FILE = "sg_weather_unified_30min.csv"
BATCH_SIZE = 20                   # Saves to disk every ~20 time steps
# ---------------------

URLS = {
    "temp": "https://api.data.gov.sg/v1/environment/air-temperature",
    "humid": "https://api.data.gov.sg/v1/environment/relative-humidity",
    "rain": "https://api.data.gov.sg/v1/environment/rainfall"
}

def fetch_metric(url, timestamp_str):
    """Helper to fetch a single metric (temp, humid, or rain)."""
    try:
        # 5 second timeout to keep the script moving
        response = requests.get(url, params={"date_time": timestamp_str}, timeout=5)
        
        # Handle Rate Limiting (HTTP 429)
        if response.status_code == 429:
            print(f"Rate limited on {url}. Sleeping 5s...")
            time.sleep(5) 
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # If one metric fails, we return None but keep the others
        return None 

def parse_metric_data(data, metric_name, master_dict):
    """
    Parses a specific API response and updates the master_dict.
    master_dict structure: { station_id: { 'name': str, 'temp': val, 'rain': val ... } }
    """
    if not data or "items" not in data or not data["items"]:
        return

    # 1. Update Station Metadata (Name/Location)
    if "metadata" in data and "stations" in data["metadata"]:
        for station in data["metadata"]["stations"]:
            s_id = station.get("id")
            s_name = station.get("name")
            
            if s_id not in master_dict:
                master_dict[s_id] = {"name": s_name}
            elif not master_dict[s_id].get("name") and s_name:
                master_dict[s_id]["name"] = s_name

    # 2. Update Readings
    reading_item = data["items"][0]
    
    for reading in reading_item.get("readings", []):
        s_id = reading.get("station_id")
        val = reading.get("value")
        
        if s_id not in master_dict:
            master_dict[s_id] = {"name": "Unknown Station"}
            
        master_dict[s_id][metric_name] = val

def main():
    current_time = datetime.strptime(START_DATE, "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(END_DATE, "%Y-%m-%d %H:%M:%S")
    
    # Headers for the unified CSV
    headers = ["timestamp", "station_id", "station_name", "temperature", "humidity", "rainfall"]
    
    # Create file with headers if it doesn't exist
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    
    buffer = []
    timestamps_processed = 0
    total_rows = 0
    
    print(f"--- Starting Unified Harvest (30-min Interval) ---")
    print(f"Range: {START_DATE} to {END_DATE}")
    
    while current_time <= end_time:
        ts_str = current_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # A dictionary to hold merged data for this specific timestamp
        timestamp_data = {} 
        
        # 1. Fetch all 3 metrics
        temp_data = fetch_metric(URLS["temp"], ts_str)
        time.sleep(0.1) 
        humid_data = fetch_metric(URLS["humid"], ts_str)
        time.sleep(0.1)
        rain_data = fetch_metric(URLS["rain"], ts_str)
        
        # 2. Merge them into one structure
        parse_metric_data(temp_data, "temperature", timestamp_data)
        parse_metric_data(humid_data, "humidity", timestamp_data)
        parse_metric_data(rain_data, "rainfall", timestamp_data)
        
        # 3. Convert merged data to CSV rows
        for s_id, info in timestamp_data.items():
            buffer.append([
                ts_str,
                s_id,
                info.get("name"),
                info.get("temperature", ""), 
                info.get("humidity", ""),
                info.get("rainfall", "")
            ])
            
        timestamps_processed += 1
        current_time += timedelta(minutes=INTERVAL_MIN)
        
        # 4. Save to disk periodically
        if timestamps_processed >= BATCH_SIZE:
            if buffer:
                with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(buffer)
                total_rows += len(buffer)
                print(f"Saved batch. Total rows: {total_rows:,} | Time: {ts_str}")
            
            buffer = []
            timestamps_processed = 0
            time.sleep(1) 

    # Final flush
    if buffer:
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(buffer)
        print(f"--- Done! ---")
        print(f"Total rows saved: {total_rows + len(buffer):,}")

if __name__ == "__main__":
    main()