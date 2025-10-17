import copy
from ortools.constraint_solver import pywrapcp

# Note: This file doesn't need pandas or requests. It only does the math.
# It assumes a pre-built time_matrix is provided.

def solve_for_best_insertion(time_matrix, current_routes, new_order_index, num_vehicles, depot_index=0):
    """
    Calculates the best vehicle and position to insert a new order.

    Args:
        time_matrix: The matrix of travel times between all locations.
        current_routes: A list of lists, where each sublist is a vehicle's current route.
        new_order_index: The index of the new order's location in the time_matrix.
        num_vehicles: The total number of vehicles in the fleet.
        depot_index: The index of the depot.

    Returns:
        A tuple: (best_vehicle_id, best_insertion_index, new_route_cost)
        Returns (None, None, float('inf')) if no valid insertion is found.
    """
    best_cost_increase = float('inf')
    best_vehicle_id = None
    best_insertion_index = None

    for vehicle_id in range(num_vehicles):
        # If a vehicle is idle or doesn't have a route yet, create a simple new route for it
        if not current_routes.get(vehicle_id):
            # Cost to go from depot -> new_order -> depot
            cost = time_matrix[depot_index][new_order_index] + time_matrix[new_order_index][depot_index]
            if cost < best_cost_increase:
                best_cost_increase = cost
                best_vehicle_id = vehicle_id
                best_insertion_index = 1 # Insert after the depot
            continue

        # Try inserting the new order at every possible position in an existing route
        original_route = current_routes[vehicle_id]
        for i in range(1, len(original_route) + 1):
            # The original cost of the segment we are breaking
            from_node = original_route[i - 1]
            to_node = original_route[i] if i < len(original_route) else depot_index
            original_segment_cost = time_matrix[from_node][to_node]

            # The new cost of inserting the order
            cost_to_new = time_matrix[from_node][new_order_index]
            cost_from_new = time_matrix[new_order_index][to_node]
            new_segment_cost = cost_to_new + cost_from_new

            cost_increase = new_segment_cost - original_segment_cost

            if cost_increase < best_cost_increase:
                best_cost_increase = cost_increase
                best_vehicle_id = vehicle_id
                best_insertion_index = i

    # We need to calculate the full cost of the new best route
    if best_vehicle_id is not None:
        new_route = list(current_routes.get(best_vehicle_id, [depot_index]))
        new_route.insert(best_insertion_index, new_order_index)
        
        # Calculate total cost of this newly proposed route
        total_cost = 0
        for i in range(len(new_route) - 1):
            total_cost += time_matrix[new_route[i]][new_route[i+1]]
        total_cost += time_matrix[new_route[-1]][depot_index] # Return to depot
        
        return (best_vehicle_id, best_insertion_index, total_cost)

    return (None, None, float('inf'))
