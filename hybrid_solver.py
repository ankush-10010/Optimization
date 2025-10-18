import random
import math
from collections import deque
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# --- Cost Calculation Utilities (from previous version) ---
def calculate_route_cost(route, time_matrix, depot_index=0):
    if not route: return 0
    cost = time_matrix[depot_index][route[0]]
    for i in range(len(route) - 1):
        cost += time_matrix[route[i]][route[i+1]]
    cost += time_matrix[route[-1]][depot_index]
    return cost

def calculate_total_cost(routes_dict, time_matrix):
    total_cost = 0
    for route in routes_dict.values():
        total_cost += calculate_route_cost(route, time_matrix)
    return total_cost

# --- LAYER 1: IMMEDIATE ASSIGNMENT (Greedy + Tabu Search) ---
# This is the same logic as your dynamic_solver_v2.py file, now part of the hybrid solver.
def greedy_insert(current_routes, new_order_index, time_matrix, num_vehicles,
                  max_stops, max_duration, depot_index=0):
    best_cost_increase = float('inf')
    best_vehicle_id, best_insertion_index = -1, -1
    for v_id in range(num_vehicles):
        route = current_routes.get(v_id, [])
        if len(route) >= max_stops: continue
        original_cost = calculate_route_cost(route, time_matrix)
        for i in range(len(route) + 1):
            temp_route = route[:]
            temp_route.insert(i, new_order_index)
            new_cost = calculate_route_cost(temp_route, time_matrix)
            if new_cost > max_duration: continue
            cost_increase = new_cost - original_cost
            if cost_increase < best_cost_increase:
                best_cost_increase = cost_increase
                best_vehicle_id, best_insertion_index = v_id, i
    if best_vehicle_id != -1:
        new_routes = {vid: r[:] for vid, r in current_routes.items()}
        if best_vehicle_id not in new_routes: new_routes[best_vehicle_id] = []
        new_routes[best_vehicle_id].insert(best_insertion_index, new_order_index)
        return new_routes
    return None

def tabu_search(initial_solution, time_matrix, max_stops, max_duration,
                iterations=50, tabu_tenure=10):
    if not initial_solution: return None
    best_solution = {vid: r[:] for vid, r in initial_solution.items()}
    best_cost = calculate_total_cost(best_solution, time_matrix)
    current_solution = {vid: r[:] for vid, r in initial_solution.items()}
    tabu_list = deque(maxlen=tabu_tenure)
    for _ in range(iterations):
        neighborhood = []
        for vehicle_id, route in current_solution.items():
            if len(route) > 1:
                for i in range(len(route)):
                    for j in range(i + 1, len(route)):
                        if (route[i], route[j]) in tabu_list or (route[j], route[i]) in tabu_list: continue
                        neighbor_route = route[:]; neighbor_route[i], neighbor_route[j] = neighbor_route[j], neighbor_route[i]
                        if calculate_route_cost(neighbor_route, time_matrix) <= max_duration:
                             neighborhood.append((vehicle_id, neighbor_route))
        if not neighborhood: break
        best_neighbor_vehicle, best_neighbor_route, best_neighbor_cost_change = -1, None, float('inf')
        for vehicle_id, neighbor_route in neighborhood:
            cost_change = calculate_route_cost(neighbor_route, time_matrix) - calculate_route_cost(current_solution[vehicle_id], time_matrix)
            if cost_change < best_neighbor_cost_change:
                best_neighbor_cost_change, best_neighbor_vehicle, best_neighbor_route = cost_change, vehicle_id, neighbor_route
        if best_neighbor_vehicle != -1:
            old_route = current_solution[best_neighbor_vehicle]
            swapped_nodes = [node for node in old_route if node not in best_neighbor_route]
            if len(swapped_nodes) == 2: tabu_list.append((swapped_nodes[0], swapped_nodes[1]))
            current_solution[best_neighbor_vehicle] = best_neighbor_route
            current_cost = calculate_total_cost(current_solution, time_matrix)
            if current_cost < best_cost:
                best_solution, best_cost = {vid: r[:] for vid, r in current_solution.items()}, current_cost
    return best_solution

def assign_new_order_realtime(new_order_index, current_routes, time_matrix, num_vehicles,
                              max_stops, max_duration):
    print("LAYER 1: Finding initial solution with Greedy Insertion...")
    greedy_solution = greedy_insert(current_routes, new_order_index, time_matrix, num_vehicles, max_stops, max_duration)
    if greedy_solution is None:
        print("LAYER 1: Greedy search could not find a valid assignment.")
        return None, "greedy"
    greedy_total_cost = calculate_total_cost(greedy_solution, time_matrix)
    print(f"LAYER 1: Greedy solution found. Total Fleet Cost: {greedy_total_cost:.2f} mins.")
    print("LAYER 1: Refining solution with Tabu Search...")
    tabu_solution = tabu_search(greedy_solution, time_matrix, max_stops, max_duration)
    if tabu_solution:
        tabu_total_cost = calculate_total_cost(tabu_solution, time_matrix)
        print(f"LAYER 1: Tabu search finished. Best Total Fleet Cost: {tabu_total_cost:.2f} mins.")
        if tabu_total_cost < greedy_total_cost * 0.97:
            print("LAYER 1: Tabu search found a significant improvement. Applying.")
            return tabu_solution, "tabu"
    print("LAYER 1: Tabu search did not find significant improvement. Using greedy solution.")
    return greedy_solution, "greedy"

# --- NEW: LAYER 2: BATCH OPTIMIZATION ---
def batch_optimization_vrp(current_routes, time_matrix, num_vehicles,
                           max_stops, max_duration, time_limit_sec=5):
    """
    Layer 2: Re-optimizes a batch of orders using Google OR-Tools' powerful VRP solver.
    """
    print("\nLAYER 2: Starting batch optimization...")
    
    # 1. Collect all orders currently in routes
    all_orders = []
    for route in current_routes.values():
        all_orders.extend(route)
    
    if not all_orders:
        print("LAYER 2: No orders to optimize.")
        return current_routes

    # The VRP solver needs a list of all unique nodes (depot + customers)
    node_indices = [0] + list(set(all_orders))
    # A map from the original node index to its new index in our small problem
    node_map = {node: i for i, node in enumerate(node_indices)}
    
    # 2. Build a smaller time matrix for just this batch of orders
    num_nodes = len(node_indices)
    batch_time_matrix = [[0] * num_nodes for _ in range(num_nodes)]
    for i in range(num_nodes):
        for j in range(num_nodes):
            original_i = node_indices[i]
            original_j = node_indices[j]
            batch_time_matrix[i][j] = time_matrix[original_i][original_j]

    # 3. Set up and solve the VRP
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return batch_time_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Add constraints
    routing.AddDimension(transit_callback_index, 0, max_duration, True, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")
    
    # Ensure every order is delivered
    for i in range(1, num_nodes):
        routing.AddDisjunction([manager.NodeToIndex(i)], 1000000)

    # 4. Solve with a time limit
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.time_limit.FromSeconds(time_limit_sec)
    solution = routing.SolveWithParameters(search_parameters)
    
    # 5. Extract and return the improved routes
    if solution:
        new_routes = {i: [] for i in range(num_vehicles)}
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                node_index_small = manager.IndexToNode(index)
                if node_index_small != 0: # Exclude depot
                    original_node_index = node_indices[node_index_small]
                    new_routes[vehicle_id].append(original_node_index)
                index = solution.Value(routing.NextVar(index))
        
        # Filter out empty routes
        new_routes = {vid: r for vid, r in new_routes.items() if r}
        
        # Check for improvement against the original routes
        new_cost = calculate_total_cost(new_routes, time_matrix)
        old_cost = calculate_total_cost(current_routes, time_matrix)
        
        print(f"LAYER 2: Batch optimization finished. Old cost: {old_cost:.2f}, New cost: {new_cost:.2f}")
        
        # As per the plan, only update if there's a >5% improvement
        if new_cost < old_cost * 0.95:
            print("LAYER 2: Found significant improvement (>5%). Applying new routes.")
            return new_routes
        else:
            print("LAYER 2: Improvement was not significant. Keeping original routes.")
            return current_routes
            
    print("LAYER 2: Batch optimization did not find a solution.")
    return current_routes
