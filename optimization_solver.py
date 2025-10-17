import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta ### NEW ###
import time ### NEW ###
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# The fixed time in minutes spent at each customer location for the delivery.
SERVICE_TIME_MINUTES = 5

### NEW: Traffic and Departure Time Configuration ###
# Set the day and hour you are planning for.
# 0 = today, 1 = tomorrow, etc.
PLANNING_DAY_OFFSET = 1
# Set the hour in 24-hour format (e.g., 11 for 11:00 AM)
PLANNING_HOUR = 11

# --- API Key Configuration (Unchanged) ---
# API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
API_KEY = "AIzaSyC_hI6BowrJPojeBiRldmuFVf3aqsSRZbg"
if API_KEY == "AIzaSyC_hI6BowrJPojeBiRldmuFVf3aqsSRZbg":
    print("WARNING: Using a placeholder API key. Please replace 'YOUR_API_KEY_HERE' with your actual Google Maps API key.")

# --- Caching (Unchanged) ---
DISTANCE_CACHE_FILE = 'distance_cache.json'
try:
    with open(DISTANCE_CACHE_FILE, 'r') as f:
        distance_cache = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    distance_cache = {}

def save_cache():
    with open(DISTANCE_CACHE_FILE, 'w') as f:
        json.dump(distance_cache, f, indent=4)

### MODIFIED: Function now accepts a departure time ###
def get_real_travel_time(lat1, lon1, lat2, lon2, departure_timestamp):
    """
    Gets the real-world travel time in MINUTES from the Google Maps Directions API,
    accounting for predictive traffic based on the departure_timestamp.
    """
    origin = f"{lat1},{lon1}"
    destination = f"{lat2},{lon2}"
    
    # The cache key now includes the timestamp to store traffic-specific data
    cache_key = f"{origin}->{destination}@{departure_timestamp}"
    
    if cache_key in distance_cache:
        return distance_cache[cache_key]
        
    # Add the departure_time parameter to the API request
    url = (f"https://maps.googleapis.com/maps/api/directions/json?"
           f"origin={origin}&destination={destination}&departure_time={departure_timestamp}"
           f"&traffic_model=best_guess&key={API_KEY}")
           
    try:
        response = requests.get(url)
        data = response.json()
        if data['status'] == 'OK':
            # Get "duration_in_traffic" if available, otherwise fall back to standard duration
            duration_seconds = data['routes'][0]['legs'][0].get('duration_in_traffic', data['routes'][0]['legs'][0]['duration'])['value']
            duration_minutes = round(duration_seconds / 60)
            distance_cache[cache_key] = duration_minutes
            return duration_minutes
        else:
            print(f"API Error for {origin}->{destination}: {data.get('status', 'Unknown Status')}")
            return 99999
    except Exception as e:
        print(f"An error occurred during API call: {e}")
        return 99999

def get_solution_for_restaurant(restaurant_name):
    # --- Data Loading (Unchanged) ---
    try:
        df_orders = pd.read_csv('order_history_kaggle_data.csv')
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        df_demand = pd.read_csv('subzone_demand_with_time.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure all CSV files are present.")
        return None, None

    # --- Data Preparation (Unchanged) ---
    try:
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains(restaurant_name, na=False)].iloc[0]
    except IndexError:
        print(f"Restaurant '{restaurant_name}' not found.")
        return None, None
    
    # ... (rest of data preparation is the same)
    customer_subzones = df_orders[df_orders['Restaurant name'] == restaurant_name]['Subzone'].unique()
    locations = [depot_info]
    demands = [0]
    time_windows = [(0, 1440)]
    location_names = [depot_info['original_address']]
    for subzone in customer_subzones:
        subzone = subzone.strip()
        loc_info = df_geocoded[df_geocoded['original_address'] == f"{subzone}, Delhi NCR"]
        demand_info = df_demand[df_demand['Subzone'] == subzone]
        if not loc_info.empty and not demand_info.empty:
            locations.append(loc_info.iloc[0])
            demands.append(demand_info['average_daily_demand'].iloc[0])
            location_names.append(loc_info.iloc[0]['original_address'])
            earliest = int(demand_info['earliest_time'].iloc[0])
            latest = int(demand_info['latest_time'].iloc[0])
            time_windows.append((earliest, latest))
    if len(locations) <= 1: return None, None
    
    ### MODIFIED: Calculate the departure timestamp ###
    # --- Create Time Matrix with Traffic Prediction ---
    now = datetime.now()
    planning_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=PLANNING_DAY_OFFSET)
    planning_datetime = planning_day.replace(hour=PLANNING_HOUR, minute=0)
    departure_timestamp = int(time.mktime(planning_datetime.timetuple()))
    
    print(f"Building traffic-aware travel time matrix for departure at: {planning_datetime.strftime('%Y-%m-%d %I:%M %p')}...")
    
    num_locations = len(locations)
    time_matrix = [[0] * num_locations for _ in range(num_locations)]
    
    for i in range(num_locations):
        for j in range(num_locations):
            if i == j:
                continue
            loc1 = locations[i]
            loc2 = locations[j]
            # Pass the timestamp to the API call function
            time_matrix[i][j] = get_real_travel_time(
                loc1['latitude'], loc1['longitude'],
                loc2['latitude'], loc2['longitude'],
                departure_timestamp
            )

    save_cache()
    print("✅ Travel time matrix built successfully.")

    # --- VRP Model Configuration and Solution (Unchanged) ---
    # ... (The rest of the file is identical to the previous version)
    num_vehicles = 10
    vehicle_capacities = [50] * num_vehicles
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel_time = time_matrix[from_node][to_node]
        service_time = SERVICE_TIME_MINUTES if to_node != 0 else 0
        return travel_time + service_time
    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    routing.AddDimension(transit_callback_index, 30, 1440, False, 'Time')
    time_dimension = routing.GetDimensionOrDie('Time')
    time_dimension.SetGlobalSpanCostCoefficient(100)
    for location_idx, time_window in enumerate(time_windows):
        if location_idx == 0: continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
    for i in range(num_vehicles):
        index = routing.Start(i)
        time_dimension.CumulVar(index).SetRange(time_windows[0][0], time_windows[0][1])
    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, vehicle_capacities, True, 'Capacity')
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.FromSeconds(10)
    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        processed_solution = []
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route_nodes = []
            route_details = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                time_var = time_dimension.CumulVar(index)
                route_nodes.append(node_index)
                route_details.append({'node': node_index, 'name': location_names[node_index], 'arrival_time': solution.Min(time_var), 'departure_time': solution.Max(time_var)})
                index = solution.Value(routing.NextVar(index))
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            route_details.append({'node': node_index, 'name': location_names[node_index], 'arrival_time': solution.Min(time_var), 'departure_time': solution.Max(time_var)})
            if len(route_nodes) > 1:
                processed_solution.append({'vehicle_id': vehicle_id, 'route_nodes': route_nodes, 'route_details': route_details, 'route_time': solution.Min(time_dimension.CumulVar(routing.End(vehicle_id)))})
        return processed_solution, locations

    return None, None