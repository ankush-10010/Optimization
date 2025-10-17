import folium
import json
import requests
from optimization_solver import get_solution_for_restaurant
import webbrowser
import os
import pandas as pd

RESTAURANT_NAME = "Swaad"
OUTPUT_MAP_FILE = 'delivery_routes_map.html'
API_KEY = "AIzaSyC_hI6BowrJPojeBiRldmuFVf3aqsSRZbg"

# Cache for polylines to avoid repeated API calls
POLYLINE_CACHE_FILE = 'polyline_cache.json'
try:
    with open(POLYLINE_CACHE_FILE, 'r') as f:
        polyline_cache = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    polyline_cache = {}

def save_polyline_cache():
    with open(POLYLINE_CACHE_FILE, 'w') as f:
        json.dump(polyline_cache, f, indent=4)

def decode_polyline(polyline_str):
    """
    Decodes a polyline string (from Google Maps API) into a list of (lat, lng) tuples.
    Reference: https://developers.google.com/maps/documentation/utilities/polylinealgorithm
    """
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20:
                    break
            if result & 1:
                changes[unit] = ~(result >> 1)
            else:
                changes[unit] = result >> 1

        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 1e5, lng / 1e5))

    return coordinates

def get_route_polyline(lat1, lon1, lat2, lon2):
    """
    Gets the actual road path geometry from Google Maps Directions API.
    Returns a list of (lat, lng) coordinates that follow the actual roads.
    """
    origin = f"{lat1},{lon1}"
    destination = f"{lat2},{lon2}"
    
    cache_key = f"{origin}->{destination}"
    
    if cache_key in polyline_cache:
        return polyline_cache[cache_key]
    
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if data['status'] == 'OK':
            polyline_str = data['routes'][0]['overview_polyline']['points']
            coordinates = decode_polyline(polyline_str)
            polyline_cache[cache_key] = coordinates
            save_polyline_cache()
            return coordinates
        else:
            print(f"API Error for {origin}->{destination}: {data.get('status', 'Unknown')}")
            return None
            
    except Exception as e:
        print(f"Error fetching polyline: {e}")
        return None

def format_time_from_start(minutes):
    """Converts minutes from a 9:00 AM start to a readable HH:MM AM/PM format."""
    start_hour = 9
    hour = start_hour + (minutes // 60)
    minute = minutes % 60
    am_pm = "AM"
    if hour >= 12:
        am_pm = "PM"
        if hour > 12:
            hour -= 12
    return f"{int(hour):02d}:{int(minute):02d} {am_pm}"

print(f"Attempting to solve and visualize routes for: {RESTAURANT_NAME}")

# 1. Get the detailed solution from our solver
solution_data, locations_data = get_solution_for_restaurant(RESTAURANT_NAME)

if not solution_data:
    print("Could not find a solution to visualize.")
else:
    print(f"✅ Solution found with {len(solution_data)} vehicles. Creating map with real road paths...")
    
    # 2. Create the base map, centered on the depot
    depot_coords = [locations_data[0]['latitude'], locations_data[0]['longitude']]
    my_map = folium.Map(location=depot_coords, zoom_start=12, tiles="cartodbpositron")
    
    # Add depot marker
    folium.Marker(
        depot_coords,
        popup=f"<strong>Depot:</strong><br>{locations_data[0]['original_address']}",
        icon=folium.Icon(color='red', icon='house')
    ).add_to(my_map)
    
    # 3. Add customer location markers with time windows
    df_demand_with_time = pd.read_csv('subzone_demand_with_time.csv')
    
    for i in range(1, len(locations_data)):
        loc = locations_data[i]
        address = loc['original_address']
        subzone_name = address.split(',')[0].strip()
        
        demand_info = df_demand_with_time[df_demand_with_time['Subzone'] == subzone_name]
        
        popup_html = f"<strong>{address}</strong>"
        if not demand_info.empty:
            earliest = demand_info.iloc[0]['earliest_time']
            latest = demand_info.iloc[0]['latest_time']
            popup_html += f"<br>Window: {format_time_from_start(earliest)} - {format_time_from_start(latest)}"
            
        folium.Marker(
            [loc['latitude'], loc['longitude']],
            popup=popup_html,
            icon=folium.Icon(color='blue', icon='info')
        ).add_to(my_map)
    
    # 4. Draw routes using actual road paths from Google Maps API
    colors = ['green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'lightblue', 'pink']
    
    print("Fetching actual road paths from Google Maps API...")
    
    for i, route_info in enumerate(solution_data):
        route_nodes = route_info['route_nodes']
        route_details = route_info['route_details']
        vehicle_id = route_info['vehicle_id']
        color = colors[i % len(colors)]
        
        # For each consecutive pair of stops, get the actual road path
        for stop_idx in range(len(route_nodes) - 1):
            from_node = route_nodes[stop_idx]
            to_node = route_nodes[stop_idx + 1]
            
            from_loc = locations_data[from_node]
            to_loc = locations_data[to_node]
            
            # Get the actual polyline (road path) for this segment
            polyline_coords = get_route_polyline(
                from_loc['latitude'], from_loc['longitude'],
                to_loc['latitude'], to_loc['longitude']
            )
            
            if polyline_coords:
                folium.PolyLine(
                    polyline_coords,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    tooltip=f"Vehicle {vehicle_id}: Stop {stop_idx + 1}"
                ).add_to(my_map)
        
        # Finally, add the return to depot
        last_node = route_nodes[-1]
        last_loc = locations_data[last_node]
        
        polyline_coords = get_route_polyline(
            last_loc['latitude'], last_loc['longitude'],
            depot_coords[0], depot_coords[1]
        )
        
        if polyline_coords:
            folium.PolyLine(
                polyline_coords,
                color=color,
                weight=4,
                opacity=0.8,
                tooltip=f"Vehicle {vehicle_id}: Return to Depot"
            ).add_to(my_map)
        
        # Add arrival time circles at each stop
        for stop in route_details:
            if stop['node'] == 0:
                continue
            
            node_index = stop['node']
            loc = locations_data[node_index]
            arrival_time = stop['arrival_time']
            
            folium.CircleMarker(
                location=[loc['latitude'], loc['longitude']],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=f"Vehicle {vehicle_id}<br>Arrives: {format_time_from_start(arrival_time)}"
            ).add_to(my_map)
    
    # 5. Save and open the map
    my_map.save(OUTPUT_MAP_FILE)
    print(f"🗺️  Map successfully saved to '{OUTPUT_MAP_FILE}'")
    
    try:
        filepath = os.path.abspath(OUTPUT_MAP_FILE)
        webbrowser.open(f"file://{filepath}")
        print("Map opened in your default web browser.")
    except Exception as e:
        print(f"Could not auto-open map. Please open '{OUTPUT_MAP_FILE}' manually.")