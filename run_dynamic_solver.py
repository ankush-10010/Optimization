import time
import random
import pandas as pd
import json
from collections import deque
from dynamic_solver import solve_for_best_insertion

# --- Configuration ---
SIMULATION_START_HOUR = 9
SIMULATION_END_HOUR = 17
MINUTES_PER_TICK = 5
PROBABILITY_OF_NEW_ORDER_PER_TICK = 0.4
NUM_VEHICLES = 3
TIME_MATRIX_FILE = 'time_matrix.json'
MAX_STOPS_PER_ROUTE = 8
MAX_ROUTE_DURATION_MINS = 180 # 3 hours

# --- Vehicle and Order classes (unchanged) ---
class Vehicle:
    def __init__(self, vehicle_id, start_location):
        self.id = vehicle_id
        self.location = start_location
        self.route = []
        self.status = "idle"
        print(f"Vehicle {self.id} created at depot {self.location['original_address']}.")

    def set_route(self, route_indices, all_locations):
        self.route = [all_locations[i] for i in route_indices]
        if self.route:
            self.status = "en_route"
            print(f"Vehicle {self.id}: Route updated. Next stop: {self.route[0]['original_address']}. Total stops: {len(self.route)}.")
        else:
            self.status = "idle"
            print(f"Vehicle {self.id}: Route complete. Now idle at depot.")

class Order:
    def __init__(self, order_id, location_index, time_placed_str):
        self.id = order_id
        self.location_index = location_index
        self.time_placed = time_placed_str
        self.status = "unassigned"


def run_full_simulation():
    print("--- Starting DYNAMIC Delivery Simulation with Constraints ---")

    # --- Load Data (unchanged) ---
    try:
        with open(TIME_MATRIX_FILE, 'r') as f:
            data = json.load(f)
        all_locations = data['locations']
        time_matrix = data['time_matrix']
        print(f"✅ Master time matrix and {len(all_locations)} locations loaded successfully.")
    except FileNotFoundError:
        print(f"Error: '{TIME_MATRIX_FILE}' not found. Run 'build_master_matrix.py' first.")
        return

    # --- Initialize Simulation (unchanged) ---
    vehicles = [Vehicle(i, start_location=all_locations[0]) for i in range(NUM_VEHICLES)]
    pending_orders = []
    current_routes = {i: [] for i in range(NUM_VEHICLES)}
    order_counter = 0

    # --- Main Simulation Loop ---
    for minute in range(SIMULATION_START_HOUR * 60, SIMULATION_END_HOUR * 60, MINUTES_PER_TICK):
        current_time_str = f"Day 1, {minute//60:02d}:{minute%60:02d}"
        print(f"\n--- {current_time_str} ---")

        # 1. Event Generator (unchanged)
        if random.random() < PROBABILITY_OF_NEW_ORDER_PER_TICK:
            order_counter += 1
            random_customer_index = random.randint(1, len(all_locations) - 1)
            new_order = Order(order_counter, random_customer_index, current_time_str)
            pending_orders.append(new_order)
            print(f"EVENT: New order #{new_order.id} for {all_locations[new_order.location_index]['original_address']}.")
            print(f"Pending orders in queue: {len(pending_orders)}")

        # --- MODIFIED: Smarter Assignment Logic ---
        # At each time step, try to assign any order from the queue, not just the first one.
        if pending_orders:
            assigned_this_tick = False
            
            # Iterate through a copy of the list so we can safely remove items
            for order_to_assign in pending_orders[:]:
                print(f"OPTIMIZING: Attempting to assign order #{order_to_assign.id}...")
                
                best_vehicle, best_index, cost = solve_for_best_insertion(
                    time_matrix,
                    current_routes,
                    order_to_assign.location_index,
                    NUM_VEHICLES,
                    MAX_STOPS_PER_ROUTE,
                    MAX_ROUTE_DURATION_MINS
                )
                
                if best_vehicle is not None:
                    print(f"SUCCESS: Assigning order #{order_to_assign.id} to Vehicle {best_vehicle}. New route duration: {int(cost)} mins.")
                    current_routes[best_vehicle].insert(best_index, order_to_assign.location_index)
                    vehicles[best_vehicle].set_route(current_routes[best_vehicle], all_locations)
                    order_to_assign.status = "assigned"
                    
                    # Remove the assigned order from the original list
                    pending_orders.remove(order_to_assign)
                    assigned_this_tick = True
                    
                    # Once we've assigned one order, we stop and wait for the next time tick
                    # This prevents one vehicle from getting multiple orders in the same tick
                    break
            
            if not assigned_this_tick:
                print("INFO: No pending orders could be assigned this tick.")

    print(f"\n--- Dynamic Simulation Ended ---")
    print(f"Orders remaining in queue: {len(pending_orders)}")

if __name__ == "__main__":
    run_full_simulation()

