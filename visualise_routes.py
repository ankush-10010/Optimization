import folium
from optimization_solver import get_solution_for_restaurant # Import our updated solver
import webbrowser
import os
import pandas as pd
RESTAURANT_NAME = "Aura Pizzas"
OUTPUT_MAP_FILE = 'delivery_routes_map.html'

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

# 1. Get the detailed solution from our new solver
solution_data, locations_data = get_solution_for_restaurant(RESTAURANT_NAME)

if not solution_data:
    print("Could not find a solution to visualize.")
else:
    print(f"✅ Solution found with {len(solution_data)} vehicles. Creating map...")
    
    # 2. Create the base map, centered on the depot (restaurant)
    depot_coords = [locations_data[0]['latitude'], locations_data[0]['longitude']]
    my_map = folium.Map(location=depot_coords, zoom_start=12, tiles="cartodbpositron")
    
    # Add a marker for the depot
    folium.Marker(
        depot_coords,
        popup=f"<strong>Depot:</strong><br>{locations_data[0]['original_address']}",
        icon=folium.Icon(color='red', icon='house')
    ).add_to(my_map)
    
    # 3. Add markers for all customer locations with their time windows
    # We need to re-load the demand data to get the time windows for popups
    df_demand_with_time = pd.read_csv('subzone_demand_with_time.csv')
    
    for i in range(1, len(locations_data)):
        loc = locations_data[i]
        address = loc['original_address']
        # Extract subzone name from "Subzone, Delhi NCR" format
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
        
    # 4. Draw the route polylines and add scheduled time markers
    colors = ['green', 'purple', 'orange', 'darkred', 'cadetblue', 'darkgreen', 'lightblue', 'pink']
    
    for i, route_info in enumerate(solution_data):
        route_nodes = route_info['route_nodes']
        route_details = route_info['route_details']
        vehicle_id = route_info['vehicle_id']
        color = colors[i % len(colors)]
        
        # Create the line for the route
        route_coords = [[locations_data[j]['latitude'], locations_data[j]['longitude']] for j in route_nodes]
        route_coords.append(depot_coords) # Add depot at the end
        
        folium.PolyLine(
            route_coords,
            color=color,
            weight=4,
            opacity=0.8,
            tooltip=f"Route for Vehicle {vehicle_id}"
        ).add_to(my_map)
        
        # Add small circles for each stop with arrival time info
        for stop in route_details:
            if stop['node'] == 0: continue # Don't re-add depot
            
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

    # 5. Save the map and auto-open it
    my_map.save(OUTPUT_MAP_FILE)
    print(f"🗺️  Map successfully saved to '{OUTPUT_MAP_FILE}'")
    
    try:
        # Get the full path to the file
        filepath = os.path.abspath(OUTPUT_MAP_FILE)
        webbrowser.open(f"file://{filepath}")
        print("Map opened in your default web browser.")
    except Exception as e:
        print(f"Could not auto-open map. Please open '{OUTPUT_MAP_FILE}' manually.")
