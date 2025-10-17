# Save this as visualize_routes.py
import folium
from optimization_solver import get_solution_for_restaurant # Import our solver

RESTAURANT_NAME = "Aura Pizzas"
OUTPUT_MAP_FILE = 'delivery_routes_map.html'

print(f"Attempting to solve and visualize routes for: {RESTAURANT_NAME}")

# 1. Get the optimized solution from our solver
solved_routes, locations_data = get_solution_for_restaurant(RESTAURANT_NAME)

if not solved_routes:
    print("Could not find a solution to visualize.")
else:
    print(f"✅ Solution found with {len(solved_routes)} vehicles. Creating map...")
    
    # 2. Create the base map, centered on the depot (restaurant)
    depot_coords = [locations_data[0]['latitude'], locations_data[0]['longitude']]
    my_map = folium.Map(location=depot_coords, zoom_start=12)
    
    # Add a marker for the depot
    folium.Marker(
        depot_coords,
        popup=f"<strong>Depot:</strong><br>{locations_data[0]['original_address']}",
        icon=folium.Icon(color='red', icon='home')
    ).add_to(my_map)
    
    # 3. Add markers for all customer locations
    for i in range(1, len(locations_data)):
        loc = locations_data[i]
        folium.Marker(
            [loc['latitude'], loc['longitude']],
            popup=f"<strong>{loc['original_address']}</strong>",
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(my_map)
        
    # 4. Draw the route polylines on the map
    colors = ['green', 'purple', 'orange', 'darkred', 'cadetblue']
    for i, route in enumerate(solved_routes):
        route_coords = [[locations_data[j]['latitude'], locations_data[j]['longitude']] for j in route]
        route_coords.append(depot_coords) # Add depot at the end to complete the loop
        
        folium.PolyLine(
            route_coords,
            color=colors[i % len(colors)],
            weight=4,
            opacity=0.8,
            tooltip=f"Route for Vehicle {i}"
        ).add_to(my_map)

    # 5. Save the map to an HTML file
    my_map.save(OUTPUT_MAP_FILE)
    print(f"🗺️  Map successfully saved to '{OUTPUT_MAP_FILE}'")
    print("Open this file in your web browser to see the interactive routes!")