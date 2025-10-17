import time
import random
import pandas as pd
from collections import deque

# --- Configuration ---
SIMULATION_START_HOUR = 9  # 9 AM
SIMULATION_END_HOUR = 17   # 5 PM
MINUTES_PER_TICK = 1       # How many minutes pass in each simulation step
PROBABILITY_OF_NEW_ORDER_PER_TICK = 0.1 # 10% chance of a new order every minute

class Vehicle:
    """Represents a delivery vehicle in the simulation."""
    def __init__(self, vehicle_id, start_location):
        self.id = vehicle_id
        self.location = start_location
        self.route = deque() # A queue of places to go
        self.status = "idle" # Can be "idle", "en_route", "delivering"
        print(f"Vehicle {self.id} created at depot {self.location['name']}.")

    def assign_route(self, route_plan):
        """Assigns a new list of stops to the vehicle."""
        # The route plan should be a list of location dictionaries
        self.route = deque(route_plan)
        self.status = "en_route"
        print(f"Vehicle {self.id}: New route assigned. First stop: {self.route[0]['name']}")

    def update(self, current_time_str):
        """Called every tick to update the vehicle's status and location."""
        if self.status == "idle":
            # Do nothing if idle
            return

        if not self.route:
            # Route is finished
            self.status = "idle"
            print(f"{current_time_str} - Vehicle {self.id}: Route complete. Returned to depot and now idle.")
            return

        # For this simple simulation, we'll just pop the next stop instantly.
        # A more advanced simulation would calculate travel time.
        next_stop = self.route.popleft()
        self.location = next_stop
        self.status = "delivering"
        print(f"{current_time_str} - Vehicle {self.id}: Arrived at {self.location['name']}.")
        # In a real simulation, you'd have a "delivering" state for a few ticks.
        self.status = "en_route" if self.route else "returning_to_depot"


class Order:
    """Represents a customer order."""
    def __init__(self, order_id, location, time_placed_str):
        self.id = order_id
        self.location = location
        self.time_placed = time_placed_str
        self.status = "unassigned"


def run_simulation():
    """Main function to run the delivery simulation."""
    print("--- Starting Delivery Simulation ---")

    # --- Load Data ---
    # We only need location data for this simulation
    try:
        df_geocoded = pd.read_csv('geocoded_locations.csv')
        # We'll use "Swaad" as our restaurant/depot for this example
        depot_info = df_geocoded[df_geocoded['original_address'].str.contains("Swaad", na=False)].iloc[0].to_dict()
        customer_locations = df_geocoded[~df_geocoded['original_address'].str.contains("Swaad", na=False)].to_dict('records')
    except (FileNotFoundError, IndexError):
        print("Error: Could not load 'geocoded_locations.csv' or find the depot 'Swaad'.")
        return

    # --- Initialize Simulation ---
    vehicles = [Vehicle(i, start_location=depot_info) for i in range(3)] # Create 3 vehicles
    pending_orders = []
    order_counter = 0

    # --- Main Simulation Loop ---
    for minute in range(SIMULATION_START_HOUR * 60, SIMULATION_END_HOUR * 60, MINUTES_PER_TICK):
        hour = minute // 60
        min_of_hour = minute % 60
        current_time_str = f"Day 1, {hour:02d}:{min_of_hour:02d}"

        print(f"\n--- {current_time_str} ---")

        # 1. Event Generator: Check for new orders
        if random.random() < PROBABILITY_OF_NEW_ORDER_PER_TICK:
            order_counter += 1
            new_order_location = random.choice(customer_locations)
            new_order = Order(order_counter, new_order_location, current_time_str)
            pending_orders.append(new_order)
            print(f"EVENT: New order #{new_order.id} received for {new_order.location['original_address']}.")

        # 2. Assignment Logic (Placeholder for Phase 2)
        # In this phase, we just check if there are pending orders and an idle vehicle.
        if pending_orders:
            for vehicle in vehicles:
                if vehicle.status == "idle" and pending_orders:
                    # Very simple logic: assign the first pending order to the first idle vehicle
                    order_to_assign = pending_orders.pop(0)
                    order_to_assign.status = "assigned"
                    print(f"ASSIGNMENT: Assigning order #{order_to_assign.id} to Vehicle {vehicle.id}.")
                    # The route is just the depot -> customer -> depot
                    route_plan = [order_to_assign.location, depot_info]
                    vehicle.assign_route(route_plan)
                    break # Stop looking for vehicles for this tick

        # 3. Update all vehicles
        for vehicle in vehicles:
            vehicle.update(current_time_str)

        # Pause for a moment to make the simulation readable in the terminal
        time.sleep(0.1)

    print("\n--- Simulation Ended ---")

if __name__ == "__main__":
    run_simulation()
