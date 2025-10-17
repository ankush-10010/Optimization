import time
import random
import pandas as pd
from collections import deque
from optimization_solver import get_real_travel_time # Use our existing API function
from dynamic_solver import solve_for_best_insertion

# --- Configuration ---
SIMULATION_START_HOUR = 9
SIMULATION_END_HOUR = 17
MINUTES_PER_TICK = 5
PROBABILITY_OF_NEW_ORDER_PER_TICK = 0.4
NUM_VEHICLES = 3
DEPOT_NAME = "Swaad"

class Vehicle:
    def __init__(self, vehicle_id, start_location):
        self.id = vehicle_id
        self.location = start_location
        self.route = [] # Now a simple list
        self.status = "idle"
        print(f"Vehicle {self.id} created at depot {self.location['original_address']}.")

    def set_route(self, route_indices, all_locations):
        self.route = [all_locations[i] for i in route_indices]
        if self.route:
            self.status = "en_route"
            print(f"Vehicle {self.id}: New route set. Next stop: {self.route[0]['original_address']}")

class Order:
    def __init__(self, order_id, location_index, time_placed_str):
        self.id = order_id
        self.location_index = location_index
        self.time_placed = time_placed_str
        self.status = "unassigned"

def run_full_simulation():
    print("--- Starting DYNAMIC Delivery Simulation ---")

    # --- Load Data and Build Time Matrix ---
    try:
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        # Create a list of all possible locations (depot is always first)
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains(DEPOT_NAME, na=False)].iloc[0]
        customer_locations = df_geocoded[~df_geocoded['original_address'].str.contains(DEPOT_NAME, na=False)]
        all_locations = [depot_info.to_dict()] + customer_locations.to_dict('records')
        
        # Build the master time matrix once
        print("Building master time matrix... (This may use the cache)")
        num_locations = len(all_locations)
        time_matrix = [[0] * num_locations for _ in range(num_locations)]
        # For a real dynamic sim, departure time should be current sim time, but for simplicity we use a fixed time
        departure_timestamp = int(time.time()) + 3600 # An hour from now
        for i in range(num_locations):
            for j in range(num_locations):
                if i == j: continue
                loc1 = all_locations[i]
                loc2 = all_locations[j]
                time_matrix[i][j] = get_real_travel_time(
                    loc1['latitude'], loc1['longitude'],
                    loc2['latitude'], loc2['longitude'],
                    departure_timestamp
                )
        print("✅ Master time matrix built.")

    except Exception as e:
        print(f"Error during data loading or matrix building: {e}")
        return

    # --- Initialize Simulation ---
    vehicles = [Vehicle(i, start_location=all_locations[0]) for i in range(NUM_VEHICLES)]
    pending_orders = []
    current_routes = {} # {vehicle_id: [node_indices]}
    order_counter = 0

    # --- Main Simulation Loop ---
    for minute in range(SIMULATION_START_HOUR * 60, SIMULATION_END_HOUR * 60, MINUTES_PER_TICK):
        current_time_str = f"Day 1, {minute//60:02d}:{minute%60:02d}"
        print(f"\n--- {current_time_str} ---")

        # 1. Event Generator
        if random.random() < PROBABILITY_OF_NEW_ORDER_PER_TICK:
            order_counter += 1
            # Get the index of a random customer location
            random_customer_index = random.randint(1, len(all_locations) - 1)
            new_order = Order(order_counter, random_customer_index, current_time_str)
            pending_orders.append(new_order)
            print(f"EVENT: New order #{new_order.id} for {all_locations[new_order.location_index]['original_address']}.")

        # 2. Dynamic Re-optimization Engine
        if pending_orders:
            order_to_assign = pending_orders.pop(0)
            
            print(f"OPTIMIZING: Finding best route for order #{order_to_assign.id}...")
            
            best_vehicle, best_index, cost = solve_for_best_insertion(
                time_matrix,
                current_routes,
                order_to_assign.location_index,
                NUM_VEHICLES
            )

            if best_vehicle is not None:
                print(f"SOLUTION: Inserting order at position {best_index} in Vehicle {best_vehicle}'s route. New route cost: {cost} mins.")
                # Update the route in our central tracking
                new_route = list(current_routes.get(best_vehicle, [0])) # Start with depot if new
                new_route.insert(best_index, order_to_assign.location_index)
                current_routes[best_vehicle] = new_route
                
                # Update the actual vehicle object
                vehicles[best_vehicle].set_route(current_routes[best_vehicle], all_locations)
                order_to_assign.status = "assigned"
            else:
                print("WARNING: Could not find a valid insertion for the new order.")
                pending_orders.append(order_to_assign) # Put it back in the queue


    print("\n--- Dynamic Simulation Ended ---")

if __name__ == "__main__":
    run_full_simulation()
