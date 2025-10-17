# Save this as optimization_solver.py
import pandas as pd
from math import radians, sin, cos, sqrt, asin
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two points on Earth."""
    R = 6371
    dLat, dLon, lat1, lat2 = map(radians, [lat2 - lat1, lon2 - lon1, lat1, lat2])
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    return R * 2 * asin(sqrt(a))

def get_solution_for_restaurant(restaurant_name):
    """
    This function now loads data, solves the VRP,
    and RETURNS the solution and location data.
    """
    # Load all data files
    try:
        df_orders = pd.read_csv('order_history_kaggle_data.csv')
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        df_demand = pd.read_csv('subzone_demand.csv')
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure all CSV files are in the same folder.")
        return None, None
    
    # --- 1. Robust Data Preparation ---
    try:
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains(restaurant_name, na=False)].iloc[0]
    except IndexError:
        return None, None

    customer_subzones = df_orders[df_orders['Restaurant name'] == restaurant_name]['Subzone'].unique()
    locations, demands, location_names = [depot_info], [0], [depot_info['original_address']]

    for subzone in customer_subzones:
        subzone = subzone.strip()
        loc_info = df_geocoded[df_geocoded['original_address'] == f"{subzone}, Delhi NCR"]
        demand_info = df_demand[df_demand['Subzone'] == subzone]
        if not loc_info.empty and not demand_info.empty:
            locations.append(loc_info.iloc[0])
            demands.append(demand_info['average_daily_demand'].iloc[0])
            location_names.append(loc_info.iloc[0]['original_address'])

    if len(locations) <= 1: return None, None
    
    # --- 2. Create the Distance Matrix ---
    num_locations = len(locations)
    dist_matrix = [[haversine_distance(l1['latitude'], l1['longitude'], l2['latitude'], l2['longitude'])
                    for l2 in locations] for l1 in locations]

    # --- 3. VRP Model Configuration & Solve ---
    num_vehicles = 10000
    vehicle_capacities = [50] * num_vehicles
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    
    def distance_callback(from_index, to_index):
        from_node, to_node = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return int(dist_matrix[from_node][to_node] * 100)
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    def demand_callback(from_index): return demands[manager.IndexToNode(from_index)]
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, vehicle_capacities, True, 'Capacity')
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = routing.SolveWithParameters(search_parameters)

    # --- 4. Extract and Return Solution ---
    if solution:
        solved_routes = []
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route.append(node_index)
                index = solution.Value(routing.NextVar(index))
            if len(route) > 1: # Only include used routes
                solved_routes.append(route)
        return solved_routes, locations
    
    return None, None