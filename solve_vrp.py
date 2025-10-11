import pandas as pd
from math import radians, sin, cos, sqrt, asin
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the distance between two points on Earth
    using the Haversine formula.
    """
    R = 6371  # Earth radius in kilometers
    
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))
    
    return R * c

def solve_for_restaurant(restaurant_name, df_orders, df_geocoded, df_demand):
    """
    Solves the Vehicle Routing Problem for a single restaurant.
    """
    print(f"\n{'='*50}")
    print(f"🚛 Starting Optimization for: {restaurant_name}")
    print(f"{'='*50}")

    # --- 1. Data Preparation ---

    # Find the sub-zones served by this restaurant
    customer_subzones = df_orders[df_orders['Restaurant name'] == restaurant_name]['Subzone'].unique()
    if len(customer_subzones) == 0:
        print(f"No delivery data found for {restaurant_name}. Skipping.")
        return

    # Get the depot (restaurant) location details
    depot_address = f"{restaurant_name}, {customer_subzones[0]}, Delhi NCR" # Heuristic to find a valid address
    depot_info = df_geocoded[df_geocoded['original_address'].str.contains(restaurant_name, na=False)].iloc[0]

    # Create a list of all locations: depot first, then customers
    locations = [depot_info]
    customer_info_list = []
    for subzone in customer_subzones:
        # Find the geocoded info for the subzone (not the restaurant in that subzone)
        info = df_geocoded[df_geocoded['original_address'] == f"{subzone}, Delhi NCR"]
        if not info.empty:
            customer_info_list.append(info.iloc[0])
    
    locations.extend(customer_info_list)
    location_names = [loc['original_address'] for loc in locations]

    # --- 2. Create the Distance Matrix ---
    
    num_locations = len(locations)
    dist_matrix = [[0] * num_locations for _ in range(num_locations)]
    for i in range(num_locations):
        for j in range(num_locations):
            loc1 = locations[i]
            loc2 = locations[j]
            dist_matrix[i][j] = haversine_distance(loc1['latitude'], loc1['longitude'], loc2['latitude'], loc2['longitude'])

    # --- 3. Create the Demands List ---

    demands = [0] # Depot demand is 0
    for subzone in customer_subzones:
         demand_row = df_demand[df_demand['Subzone'] == subzone]
         if not demand_row.empty:
             demands.append(demand_row['average_daily_demand'].iloc[0])
         else:
             demands.append(1) # Default demand if not found

    # --- 4. VRP Model Configuration ---

    # Problem parameters
    num_vehicles = 5
    vehicle_capacities = [20] * num_vehicles # Each vehicle can carry 20 orders
    depot_index = 0

    # Create the routing index manager and routing model
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    # --- 5. Define Callbacks ---

    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(dist_matrix[from_node][to_node] * 100) # Scale to integer
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Demand and Capacity callback
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # slack
        vehicle_capacities,
        True,  # start cumul to zero
        'Capacity'
    )

    # --- 6. Solve the Problem ---

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.FromSeconds(5)

    print("🧠 Solver running...")
    solution = routing.SolveWithParameters(search_parameters)
    
    # --- 7. Print the Solution ---

    if solution:
        print("✅ Solution found!\n")
        total_distance = 0
        total_load = 0
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            plan_output = f'Route for vehicle {vehicle_id}:\n'
            route_distance = 0
            route_load = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += demands[node_index]
                plan_output += f' {location_names[node_index]} (Load: {route_load}) ->'
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
            
            # Add final leg back to depot
            plan_output += f' {location_names[manager.IndexToNode(index)]}\n'
            plan_output += f'   Distance of the route: {route_distance/100:.2f} km\n'
            plan_output += f'   Load of the route: {route_load}\n'

            if route_distance > 0: # Only print routes that are used
                print(plan_output)
                total_distance += route_distance
                total_load += route_load

        print(f'Total distance of all routes: {total_distance/100:.2f} km')
        print(f'Total orders delivered: {total_load}')
    else:
        print('❌ No solution found!')


if __name__ == '__main__':
    # Load all data files
    try:
        df_orders_history = pd.read_csv('order_history_kaggle_data.csv')
        df_geocoded_locations = pd.read_csv('geocoded_locations.csv')
        df_subzone_demand = pd.read_csv('subzone_demand.csv')
    except FileNotFoundError as e:
        print(f"Error loading files: {e}. Make sure all CSV files are in the same folder.")
        exit()
    
    # --- Run the solver for a specific restaurant ---
    # We choose "Swaad" as it serves multiple locations in the dataset
    solve_for_restaurant("Swaad", df_orders_history, df_geocoded_locations, df_subzone_demand)
    
    # You can uncomment the lines below to run for other restaurants
    # solve_for_restaurant("Tandoori Junction", df_orders_history, df_geocoded_locations, df_subzone_demand)
    # solve_for_restaurant("Dilli Burger Adda", df_orders_history, df_geocoded_locations, df_subzone_demand)