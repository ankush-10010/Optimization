import pandas as pd
from math import radians, sin, cos, sqrt, asin
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two points on Earth in kilometers."""
    R = 6371  # Earth radius in kilometers
    dLat, dLon, lat1, lat2 = map(radians, [lat2 - lat1, lon2 - lon1, lat1, lat2])
    a = sin(dLat / 2)**2 + cos(lat1) * cos(lat2) * sin(dLon / 2)**2
    return R * 2 * asin(sqrt(a))

def get_solution_for_restaurant(restaurant_name):
    """
    Loads data, solves the Vehicle Routing Problem with Time Windows (VRPTW),
    and returns the detailed solution and location data.
    """
    # Load all data files
    try:
        df_orders = pd.read_csv('order_history_kaggle_data.csv')
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        # MODIFIED: Load the data with time windows
        df_demand = pd.read_csv('subzone_demand_with_time.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure all CSV files are in the same folder.")
        return None, None

    # --- 1. Robust Data Preparation ---
    try:
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains(restaurant_name, na=False)].iloc[0]
    except IndexError:
        print(f"Restaurant '{restaurant_name}' not found in geocoded data.")
        return None, None

    customer_subzones = df_orders[df_orders['Restaurant name'] == restaurant_name]['Subzone'].unique()
    
    # Initialize lists for VRP data
    locations = [depot_info]
    demands = [0] # Depot has 0 demand
    time_windows = [(0, 1440)] # Depot open all day (e.g., 24 hours in minutes)
    location_names = [depot_info['original_address']]

    for subzone in customer_subzones:
        subzone = subzone.strip()
        loc_info = df_geocoded[df_geocoded['original_address'] == f"{subzone}, Delhi NCR"]
        demand_info = df_demand[df_demand['Subzone'] == subzone]
        if not loc_info.empty and not demand_info.empty:
            locations.append(loc_info.iloc[0])
            demands.append(demand_info['average_daily_demand'].iloc[0])
            location_names.append(loc_info.iloc[0]['original_address'])
            
            # NEW: Add time window for the customer
            earliest = int(demand_info['earliest_time'].iloc[0])
            latest = int(demand_info['latest_time'].iloc[0])
            time_windows.append((earliest, latest))

    if len(locations) <= 1:
        print(f"Not enough customer locations for restaurant '{restaurant_name}'.")
        return None, None

    # --- 2. Create Distance and Time Matrices ---
    num_locations = len(locations)
    dist_matrix = [[haversine_distance(l1['latitude'], l1['longitude'], l2['latitude'], l2['longitude'])
                    for l2 in locations] for l1 in locations]

    # --- 3. VRP Model Configuration with Time Windows ---
    num_vehicles = 10  # A more reasonable number of vehicles
    vehicle_capacities = [50] * num_vehicles
    
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, 0) # 0 is the depot index
    routing = pywrapcp.RoutingModel(manager)

    # --- Time Callback and Dimension ---
    def time_callback(from_index, to_index):
        """Returns the travel time between two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        distance = dist_matrix[from_node][to_node]
        # Assuming average speed of 40 km/h, convert distance to minutes
        # (distance / speed) * 60
        travel_time = (distance / 40) * 60 
        return int(travel_time)

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    
    # MODIFIED: Set the cost to be the travel time
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Time Windows constraint
    routing.AddDimension(
        transit_callback_index,
        30,      # Slack: max waiting time at a location (30 minutes)
        1440,    # Vehicle total time capacity (24 hours in minutes)
        False,   # Don't force start cumulative time to zero
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    # Add time window constraints for each location
    for location_idx, time_window in enumerate(time_windows):
        if location_idx == 0: continue # Skip depot
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

    # Add time window constraints for each vehicle's start node (depot)
    for i in range(num_vehicles):
        index = routing.Start(i)
        time_dimension.CumulVar(index).SetRange(time_windows[0][0], time_windows[0][1])

    # --- Demand Callback and Dimension (Capacity) ---
    def demand_callback(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,                 # No slack for capacity
        vehicle_capacities,
        True,              # Start cumul to zero
        'Capacity'
    )

    # --- 4. Solve the Model ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.FromSeconds(5) # Add a time limit

    solution = routing.SolveWithParameters(search_parameters)

    # --- 5. Extract and Return Detailed Solution ---
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
                route_details.append({
                    'node': node_index,
                    'name': location_names[node_index],
                    'arrival_time': solution.Min(time_var),
                    'departure_time': solution.Max(time_var)
                })
                index = solution.Value(routing.NextVar(index))
            
            # Add the final depot stop to the details
            node_index = manager.IndexToNode(index)
            time_var = time_dimension.CumulVar(index)
            route_details.append({
                'node': node_index,
                'name': location_names[node_index],
                'arrival_time': solution.Min(time_var),
                'departure_time': solution.Max(time_var)
            })

            if len(route_nodes) > 1: # Only include routes that are used
                processed_solution.append({
                    'vehicle_id': vehicle_id,
                    'route_nodes': route_nodes,
                    'route_details': route_details,
                    'route_time': solution.Min(time_dimension.CumulVar(routing.End(vehicle_id)))
                })
        return processed_solution, locations

    print("No solution found.")
    return None, None