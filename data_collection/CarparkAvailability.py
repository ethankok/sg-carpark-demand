import requests
import csv
import time
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
START_DATE = "2024-01-01 00:00:00"
END_DATE   = "2024-01-02 00:00:00"  # Set this to a later date for more data
INTERVAL_MIN = 30                 # Resolution (e.g., every 30 mins)
OUTPUT_FILE = "hdb_carpark_huge_dataset.csv"
BATCH_SIZE = 50                   # Write to disk after this many API calls
# ---------------------

def fetch_data(target_time):
    """Fetches data for a specific timestamp with retry logic."""
    url = "https://api.data.gov.sg/v1/transport/carpark-availability"
    timestamp_str = target_time.strftime("%Y-%m-%dT%H:%M:%S")
    params = {"date_time": timestamp_str}
    
    attempts = 0
    max_attempts = 3
    
    while attempts < max_attempts:
        try:
            # 5-second timeout to prevent hanging
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 429:
                print(f"Rate limited! Sleeping for 10s...")
                time.sleep(10)
                attempts += 1
                continue
                
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            attempts += 1
            time.sleep(2)
            if attempts == max_attempts:
                print(f"Failed to fetch {timestamp_str}: {e}")
                return None

def process_response(data, requested_time):
    """Parses the JSON response into a flat list of rows."""
    rows = []
    if not data or "items" not in data or not data["items"]:
        return rows

    item = data["items"][0]
    actual_timestamp = item.get("timestamp") # The server's actual data time

    for carpark in item.get("carpark_data", []):
        info = carpark.get("carpark_info", [])[0]
        rows.append([
            requested_time.strftime("%Y-%m-%dT%H:%M:%S"),
            actual_timestamp,
            carpark.get("carpark_number"),
            info.get("total_lots"),
            info.get("lots_available"),
            info.get("lot_type")
        ])
    return rows

def main():
    current_time = datetime.strptime(START_DATE, "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(END_DATE, "%Y-%m-%d %H:%M:%S")
    
    # Headers for the CSV
    headers = ["timestamp_requested", "timestamp_actual", "carpark_number", "total_lots", "lots_available", "lot_type"]
    
    # Initialize file with headers if it doesn't exist
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
    
    buffer = []
    api_calls = 0
    total_rows = 0
    
    print(f"--- Starting Harvest ---")
    print(f"Range: {START_DATE} to {END_DATE}")
    print(f"Interval: {INTERVAL_MIN} minutes")
    
    while current_time <= end_time:
        data = fetch_data(current_time)
        new_rows = process_response(data, current_time)
        
        if new_rows:
            buffer.extend(new_rows)
            
        api_calls += 1
        current_time += timedelta(minutes=INTERVAL_MIN)
        
        # Flush buffer to disk every BATCH_SIZE calls
        if api_calls >= BATCH_SIZE:
            with open(OUTPUT_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(buffer)
            
            total_rows += len(buffer)
            print(f"Saved batch. Total rows collected: {total_rows:,} | Current Time: {current_time}")
            buffer = [] # Clear memory
            api_calls = 0
            
            # Sleep slightly to be kind to the server
            time.sleep(1)

    # Write any remaining data in the buffer
    if buffer:
        with open(OUTPUT_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(buffer)
        total_rows += len(buffer)

    print(f"--- Done! ---")
    print(f"Total rows saved: {total_rows:,}")
    print(f"File: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()