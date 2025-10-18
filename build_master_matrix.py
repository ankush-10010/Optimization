import pandas as pd
import json
import time
from optimization_solver import get_real_travel_time

DEPOT_NAME = "Swaad"
OUTPUT_FILE = 'time_matrix.json'

def build_and_save_matrix():
    print("--- Starting Master Time Matrix Builder ---")
    
    # --- MODIFIED: More specific error handling ---
    try:
        print("Step 1: Loading 'geocoded_locations.csv'...")
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        print("...File loaded successfully.")
    except FileNotFoundError:
        print("\nFATAL ERROR: The file 'geocoded_locations.csv' was not found.")
        print("Please make sure it is in the same folder as the script.")
        return # Exit the function

    try:
        print(f"Step 2: Finding depot named '{DEPOT_NAME}'...")
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains(DEPOT_NAME, na=False)].iloc[0]
        print("...Depot found successfully.")
    except IndexError:
        print(f"\nFATAL ERROR: The depot '{DEPOT_NAME}' could not be found in 'geocoded_locations.csv'.")
        print("Please check the DEPOT_NAME variable in this script or the contents of your CSV file.")
        return # Exit the function

    # --- Data processing logic (unchanged) ---
    try:
        customer_locations = df_geocoded[~df_geocoded['original_address'].str.contains(DEPOT_NAME, na=False)]
        customer_locations = customer_locations.sort_values(by='original_address').reset_index(drop=True)
        all_locations = [depot_info.to_dict()] + customer_locations.to_dict('records')
        num_locations = len(all_locations)
        
        print(f"Step 3: Found {num_locations} total locations (1 depot + {num_locations - 1} customers).")
        print("Building matrix... This may take a long time on the first run.")

        departure_timestamp = int(time.time()) + (3600 * 24)
        time_matrix = [[0] * num_locations for _ in range(num_locations)]
        
        for i in range(num_locations):
            for j in range(num_locations):
                if i == j: continue
                loc1 = all_locations[i]
                loc2 = all_locations[j]
                time_matrix[i][j] = get_real_travel_time(
                    loc1['latitude'], loc1['longitude'],
                    loc2['latitude'], loc2['longitude'],
                    departure_timestamp
                )
            print(f"Computed routes for location {i+1}/{num_locations}...")

        output_data = {"locations": all_locations, "time_matrix": time_matrix}
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(output_data, f)
            
        print(f"\n✅ Master time matrix successfully built and saved to '{OUTPUT_FILE}'")

    except Exception as e:
        print(f"\nAn unexpected error occurred during matrix building: {e}")


if __name__ == "__main__":
    build_and_save_matrix()
