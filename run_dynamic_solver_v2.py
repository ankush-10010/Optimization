import time
import random
import json

from dynamic_solver_v2 import assign_new_order_realtime

# --- Configuration ---
SIMULATION_START_HOUR = 9
SIMULATION_END_HOUR = 17
MINUTES_PER_TICK = 15
PROBABILITY_OF_NEW_ORDER_PER_TICK = 0.9
NUM_VEHICLES = 4
TIME_MATRIX_FILE = 'time_matrix.json'

# Your strict constraint of 2 hours
MAX_ROUTE_DURATION_MINS = 170
MAX_STOPS_PER_ROUTE = 10


# --- Vehicle and Order classes (unchanged) ---
class Order:
    def __init__(self, order_id, location_index):
        self.id = order_id
        self.location_index = location_index


def run_hybrid_simulation():
    print("--- Starting HYBRID DYNAMIC Delivery Simulation (Layer 1 - Gridlock Fix) ---")

    try:
        with open(TIME_MATRIX_FILE, 'r') as f:
            data = json.load(f)
        all_locations = data['locations']
        time_matrix = data['time_matrix']
        print(f"✅ Master time matrix and {len(all_locations)} locations loaded successfully.")
    except FileNotFoundError:
        print(f"Error: '{TIME_MATRIX_FILE}' not found. Run 'build_master_matrix.py' first.")
        return

    pending_orders = []
    current_routes = {i: [] for i in range(NUM_VEHICLES)}
    order_counter = 0

    # --- Main Simulation Loop ---
    for minute in range(SIMULATION_START_HOUR * 60, SIMULATION_END_HOUR * 60, MINUTES_PER_TICK):
        current_time_str = f"Day 1, {minute//60:02d}:{minute%60:02d}"
        print(f"\n{'='*15} {current_time_str} {'='*15}")

        # 1. Event Generator
        if random.random() < PROBABILITY_OF_NEW_ORDER_PER_TICK:
            order_counter += 1
            random_customer_index = random.randint(1, len(all_locations) - 1)
            new_order = Order(order_counter, random_customer_index)
            pending_orders.append(new_order)
            print(f"EVENT: New order #{new_order.id} received for {all_locations[new_order.location_index]['original_address'].split(',')[0]}.")
            print(f"Total pending orders: {len(pending_orders)}")

        # --- MODIFIED: True Smart Queue Logic ---
        if pending_orders:
            assigned_in_tick = False
            # Iterate through a copy of the list so we can safely remove from the original
            for order_to_assign in pending_orders[:]:
                print(f"\nAttempting to assign Order #{order_to_assign.id}...")
                
                final_routes, method = assign_new_order_realtime(
                    order_to_assign.location_index,
                    current_routes,
                    time_matrix,
                    NUM_VEHICLES,
                    MAX_STOPS_PER_ROUTE,
                    MAX_ROUTE_DURATION_MINS
                )

                if final_routes:
                    print(f"SUCCESS: Order #{order_to_assign.id} assigned via {method} method.")
                    current_routes = final_routes
                    
                    # Remove the assigned order from the actual queue
                    pending_orders.remove(order_to_assign)
                    assigned_in_tick = True
                    
                    # Stop trying to assign for this tick to move to the next time step
                    break 
            
            if assigned_in_tick:
                 print("\n--- CURRENT FLEET STATUS ---")
                 for v_id, route in sorted(current_routes.items()):
                     if route:
                         route_str = ' -> '.join([all_locations[i]['original_address'].split(',')[0] for i in route])
                         print(f"Vehicle {v_id} (Stops: {len(route)}): Depot -> {route_str} -> Depot")
            else:
                print("\nINFO: No pending orders could be assigned in this time tick.")

        time.sleep(0.5)

    print("\n--- Dynamic Simulation Ended ---")
    print(f"Unassigned orders remaining in standard queue: {len(pending_orders)}")


if __name__ == "__main__":
    run_hybrid_simulation()

