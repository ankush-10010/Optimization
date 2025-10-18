import time
import random
import json
import threading
from hybrid_solver import assign_new_order_realtime, batch_optimization_vrp, calculate_route_cost

# --- Configuration ---
SIMULATION_START_HOUR = 9
SIMULATION_END_HOUR = 17
MINUTES_PER_TICK = 15
PROBABILITY_OF_NEW_ORDER_PER_TICK = 0.9
NUM_VEHICLES = 4
TIME_MATRIX_FILE = 'time_matrix.json'
MAX_ROUTE_DURATION_MINS = 150
MAX_STOPS_PER_ROUTE = 10
LAYER_2_INTERVAL_SECONDS = 30 # Run batch optimization every 30 seconds

# --- Shared State ---
# These variables will be accessed by both the main thread and the background thread
current_routes = {}
pending_orders = []
state_lock = threading.Lock() # A lock to prevent race conditions
simulation_running = True

# --- Layer 2 Worker Thread ---
def layer2_worker(time_matrix):
    """A function that runs in a separate thread to perform batch optimization."""
    global current_routes
    while simulation_running:
        time.sleep(LAYER_2_INTERVAL_SECONDS)
        
        with state_lock:
            # Work on a copy of the current routes to not block the main thread for long
            routes_to_optimize = {vid: r[:] for vid, r in current_routes.items()}

        # Run the heavy computation outside the lock
        optimized_routes = batch_optimization_vrp(
            routes_to_optimize, time_matrix, NUM_VEHICLES,
            MAX_STOPS_PER_ROUTE, MAX_ROUTE_DURATION_MINS
        )

        with state_lock:
            # Safely update the global state with the new routes
            current_routes = optimized_routes
            print("--- FLEET STATUS (Updated by Layer 2) ---")
            for v_id, route in sorted(current_routes.items()):
                 if route:
                     route_str = ' -> '.join([all_locations[i]['original_address'].split(',')[0] for i in route])
                     print(f"Vehicle {v_id} (Stops: {len(route)}): Depot -> {route_str} -> Depot")


def run_hybrid_simulation():
    """Main function to run the simulation with the hybrid architecture."""
    global current_routes, pending_orders, simulation_running, all_locations

    print("--- Starting HYBRID DYNAMIC Delivery Simulation (Layer 1 + Layer 2) ---")
    
    try:
        with open(TIME_MATRIX_FILE, 'r') as f: data = json.load(f)
        all_locations, time_matrix = data['locations'], data['time_matrix']
        print(f"✅ Master time matrix and {len(all_locations)} locations loaded successfully.")
    except FileNotFoundError:
        print(f"Error: '{TIME_MATRIX_FILE}' not found. Run 'build_master_matrix.py' first."); return

    # --- Initialize Simulation ---
    current_routes = {i: [] for i in range(NUM_VEHICLES)}
    order_counter = 0

    # --- Start the Layer 2 background thread ---
    layer2_thread = threading.Thread(target=layer2_worker, args=(time_matrix,), daemon=True)
    layer2_thread.start()
    print("✅ Layer 2 background optimization thread started.")

    # --- Main Simulation Loop (Layer 1) ---
    for minute in range(SIMULATION_START_HOUR * 60, SIMULATION_END_HOUR * 60, MINUTES_PER_TICK):
        current_time_str = f"Day 1, {minute//60:02d}:{minute%60:02d}"
        print(f"\n{'='*15} {current_time_str} {'='*15}")
        
        if random.random() < PROBABILITY_OF_NEW_ORDER_PER_TICK:
            order_counter += 1
            new_order_idx = random.randint(1, len(all_locations) - 1)
            pending_orders.append({'id': order_counter, 'index': new_order_idx})
            print(f"EVENT: New order #{order_counter} received for {all_locations[new_order_idx]['original_address'].split(',')[0]}.")

        if pending_orders:
            order_to_assign = pending_orders.pop(0)
            
            with state_lock: # Aquire lock before reading/writing shared state
                final_routes, method = assign_new_order_realtime(
                    order_to_assign['index'], current_routes, time_matrix,
                    NUM_VEHICLES, MAX_STOPS_PER_ROUTE, MAX_ROUTE_DURATION_MINS
                )
                if final_routes:
                    current_routes = final_routes
                    print("--- FLEET STATUS (Updated by Layer 1) ---")
                    for v_id, route in sorted(current_routes.items()):
                         if route:
                             route_str = ' -> '.join([all_locations[i]['original_address'].split(',')[0] for i in route])
                             print(f"Vehicle {v_id} (Stops: {len(route)}): Depot -> {route_str} -> Depot")
                else:
                    print(f"WARNING: Could not assign order #{order_to_assign['id']}. Placing back in queue.")
                    pending_orders.insert(0, order_to_assign)
        
        time.sleep(1)

    # --- End of Day Processing ---
    simulation_running = False # Signal the background thread to stop
    print("\n--- Dynamic Simulation Ended ---")
    
    # Give the background thread a moment to finish its last run
    time.sleep(LAYER_2_INTERVAL_SECONDS + 2) 
    
    # --- Premium Vehicle Logic ---
    if pending_orders:
        print("\n--- Deploying PREMIUM Vehicle for remaining orders ---")
        premium_route = []
        last_stop = 0
        while pending_orders:
            order = pending_orders.pop(0)
            premium_route.append(order['index'])
        premium_cost = calculate_route_cost(premium_route, time_matrix)
        route_str = ' -> '.join([all_locations[i]['original_address'].split(',')[0] for i in premium_route])
        print(f"Premium Vehicle Route (Stops: {len(premium_route)}): Depot -> {route_str} -> Depot")
        print(f"Premium Route Duration: {premium_cost:.2f} mins.")
    else:
        print("All orders were assigned to the standard fleet.")

if __name__ == "__main__":
    run_hybrid_simulation()