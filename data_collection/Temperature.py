import requests
import csv
import time
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
START_DATE = "2024-01-01 00:00:00"
END_DATE   = "2024-01-02 00:00:00"
INTERVAL_MIN = 30
OUTPUT_FILE = "weather_temperature.csv"
BATCH_SIZE = 50
# ---------------------

def fetch_data(target_time):
    url = "https://api.data.gov.sg/v1/environment/air-temperature"
    params = {"date_time": target_time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 429:
            time.sleep(10)
            return None
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def process_data(data, requested_time):
    rows = []
    if not data or "items" not in data or not data["items"]: return rows

    # Create a map for station names
    station_map = {}
    if "metadata" in data and "stations" in data["metadata"]:
        for s in data["metadata"]["stations"]:
            station_map[s["id"]] = s["name"]

    item = data["items"][0]
    actual_ts = item.get("timestamp")

    for reading in item.get("readings", []):
        s_id = reading.get("station_id")
        rows.append([
            requested_time.strftime("%Y-%m-%dT%H:%M:%S"),
            actual_ts,
            s_id,
            station_map.get(s_id, "Unknown"),
            reading.get("value")
        ])
    return rows

def main():
    current = datetime.strptime(START_DATE, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(END_DATE, "%Y-%m-%d %H:%M:%S")
    
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["timestamp_requested", "timestamp_actual", "station_id", "station_name", "temperature"])

    print(f"--- Fetching TEMPERATURE ---")
    
    buffer = []
    while current <= end:
        data = fetch_data(current)
        if data: buffer.extend(process_data(data, current))
        
        if len(buffer) >= (BATCH_SIZE * 10): # Flush periodically
            with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(buffer)
            print(f"Saved {len(buffer)} rows. Current: {current}")
            buffer = []
        
        current += timedelta(minutes=INTERVAL_MIN)
        time.sleep(0.2) # Small delay

    if buffer:
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(buffer)
    print("Done (Temperature).")

if __name__ == "__main__":
    main()