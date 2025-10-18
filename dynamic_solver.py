def calculate_route_cost(route, time_matrix, depot_index=0):
    """Calculates the total time/cost of a given route."""
    if not route:
        return 0
    
    total_cost = 0
    # Cost from depot to the first stop
    total_cost += time_matrix[depot_index][route[0]]
    
    # Cost between stops
    for i in range(len(route) - 1):
        total_cost += time_matrix[route[i]][route[i+1]]
        
    # Cost from the last stop back to the depot
    total_cost += time_matrix[route[-1]][depot_index]
    
    return total_cost


def solve_for_best_insertion(time_matrix, current_routes, new_order_index, num_vehicles,
                             max_stops_per_route, max_route_duration, depot_index=0):
    """
    Calculates the best vehicle and position to insert a new order,
    respecting the new constraints.
    """
    best_cost_increase = float('inf')
    best_vehicle_id = None
    best_insertion_index = None
    final_route_cost = 0

    for vehicle_id in range(num_vehicles):
        original_route = current_routes.get(vehicle_id, [])
        
        # --- CONSTRAINT CHECK ---
        if len(original_route) >= max_stops_per_route:
            continue # Skip this vehicle, it's full

        original_cost = calculate_route_cost(original_route, time_matrix)

        # Try inserting the new order at every possible position
        for i in range(len(original_route) + 1):
            temp_route = original_route[:]
            temp_route.insert(i, new_order_index)
            
            new_cost = calculate_route_cost(temp_route, time_matrix)
            
            # --- CONSTRAINT CHECK ---
            if new_cost > max_route_duration:
                continue # Skip this insertion, it makes the route too long

            cost_increase = new_cost - original_cost

            if cost_increase < best_cost_increase:
                best_cost_increase = cost_increase
                best_vehicle_id = vehicle_id
                best_insertion_index = i
                final_route_cost = new_cost

    if best_vehicle_id is not None:
        return (best_vehicle_id, best_insertion_index, final_route_cost)

    return (None, None, float('inf'))

