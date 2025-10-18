import random
import math
from collections import deque

def calculate_route_cost(route, time_matrix, depot_index=0):
    """Calculates the total time/cost of a single route."""
    if not route:
        return 0
    cost = time_matrix[depot_index][route[0]]
    for i in range(len(route) - 1):
        cost += time_matrix[route[i]][route[i+1]]
    cost += time_matrix[route[-1]][depot_index]
    return cost

def calculate_total_cost(routes_dict, time_matrix):
    """Calculates the total cost for all routes."""
    total_cost = 0
    for route in routes_dict.values():
        total_cost += calculate_route_cost(route, time_matrix)
    return total_cost

def greedy_insert(current_routes, new_order_index, time_matrix, num_vehicles,
                  max_stops, max_duration, depot_index=0):
    """The baseline greedy insertion algorithm."""
    best_cost_increase = float('inf')
    best_vehicle_id = -1
    best_insertion_index = -1
    
    for v_id in range(num_vehicles):
        route = current_routes.get(v_id, [])
        if len(route) >= max_stops:
            continue

        original_cost = calculate_route_cost(route, time_matrix)
        for i in range(len(route) + 1):
            temp_route = route[:]
            temp_route.insert(i, new_order_index)
            new_cost = calculate_route_cost(temp_route, time_matrix)
            
            if new_cost > max_duration:
                continue
                
            cost_increase = new_cost - original_cost
            if cost_increase < best_cost_increase:
                best_cost_increase = cost_increase
                best_vehicle_id = v_id
                best_insertion_index = i

    if best_vehicle_id != -1:
        new_routes = {vid: r[:] for vid, r in current_routes.items()}
        if best_vehicle_id not in new_routes:
            new_routes[best_vehicle_id] = []
        new_routes[best_vehicle_id].insert(best_insertion_index, new_order_index)
        return new_routes

    return None

def tabu_search(initial_solution, time_matrix, max_stops, max_duration,
                iterations=50, tabu_tenure=10):
    """Layer 1 Refinement: Improves a solution using Tabu Search."""
    if not initial_solution:
        return None

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
                        neighbor_route = route[:]
                        neighbor_route[i], neighbor_route[j] = neighbor_route[j], neighbor_route[i]
                        if (route[i], route[j]) in tabu_list or (route[j], route[i]) in tabu_list:
                            continue
                        new_cost = calculate_route_cost(neighbor_route, time_matrix)
                        if new_cost <= max_duration:
                             neighborhood.append((vehicle_id, neighbor_route))
        
        if not neighborhood:
            break

        best_neighbor_vehicle = -1
        best_neighbor_route = None
        best_neighbor_cost_change = float('inf')

        for vehicle_id, neighbor_route in neighborhood:
            original_cost = calculate_route_cost(current_solution[vehicle_id], time_matrix)
            new_cost = calculate_route_cost(neighbor_route, time_matrix)
            cost_change = new_cost - original_cost
            if cost_change < best_neighbor_cost_change:
                best_neighbor_cost_change = cost_change
                best_neighbor_vehicle = vehicle_id
                best_neighbor_route = neighbor_route

        if best_neighbor_vehicle != -1:
            old_route = current_solution[best_neighbor_vehicle]
            swapped_nodes = [node for node in old_route if node not in best_neighbor_route]
            if len(swapped_nodes) == 2:
                 tabu_list.append((swapped_nodes[0], swapped_nodes[1]))
            current_solution[best_neighbor_vehicle] = best_neighbor_route
            current_cost = calculate_total_cost(current_solution, time_matrix)
            if current_cost < best_cost:
                best_solution = {vid: r[:] for vid, r in current_solution.items()}
                best_cost = current_cost
                
    return best_solution


def assign_new_order_realtime(new_order_index, current_routes, time_matrix, num_vehicles,
                              max_stops, max_duration):
    """The main Layer 1 function that orchestrates the tiered assignment."""
    print("LAYER 1: Finding initial solution with Greedy Insertion...")
    greedy_solution = greedy_insert(current_routes, new_order_index, time_matrix,
                                    num_vehicles, max_stops, max_duration)

    if greedy_solution is None:
        print("LAYER 1: Greedy search could not find a valid assignment.")
        return None, "greedy"

    ### MODIFIED: Clearer logging ###
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
        else:
            print("LAYER 1: Tabu search did not find significant improvement. Using greedy solution.")
            return greedy_solution, "greedy"
    
    return greedy_solution, "greedy"

