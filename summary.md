1. Problem Statement
Modern e-commerce and food delivery platforms operate in a dynamic, unpredictable environment. While planning optimal routes at the start of the day is a good first step, this static approach fails to account for new orders that arrive after drivers are already on the road. A purely greedy approach of assigning the nearest driver to a new order can lead to severe imbalances, with some drivers being massively overworked while others remain idle.

This project addresses the challenge of real-time fleet management. It moves beyond static, pre-planned routes to a dynamic simulation that can intelligently assign new, incoming orders to a fleet of vehicles on the fly, while respecting a complex set of real-world business constraints like driver workload and maximum route times.

2. Current Project Functioning
The project has evolved from a simple route planner into a sophisticated, two-stage dynamic simulation system. It no longer creates a single, static plan. Instead, it simulates an entire day of operations, reacting to random events and making intelligent decisions in real-time.

The workflow is as follows:

Stage 1: Pre-computation (Run Once)

The build_master_matrix.py script is executed once.

It takes a designated depot (e.g., "Swaad") and calculates the real-world, traffic-aware travel time between that depot and every other possible delivery location in the dataset using the Google Maps API.

This slow but essential step produces a time_matrix.json file, which acts as a complete "knowledge base" of travel times for the simulation.

Stage 2: Dynamic Simulation (Run Anytime)

The run_dynamic_simulation.py script is executed.

It instantly loads the pre-computed time_matrix.json.

It starts a time loop, simulating a full workday minute by minute.

Throughout the day, it randomly generates new customer orders.

For each new order, it uses the dynamic_solver to find the most efficient vehicle and route insertion point without violating business rules (like maximum stops or route duration).

It prints a real-time log of all events, decisions, and assignments to the console, showing how the fleet is managed throughout the day.

3. File Summary and Their Roles
Your project now consists of a suite of specialized Python scripts, each with a distinct and important role.

Core Data & API Files:
optimization_solver.py

What it does: This file now serves as a powerful utility library. Its most important function is get_real_travel_time, which handles all communication with the Google Maps Directions API, including caching and traffic prediction logic. It still contains the original static solver (get_solution_for_restaurant), but that function is no longer used by the dynamic simulation.

Simulation Pre-computation File:
build_master_matrix.py

What it does: This is the data preparation engine. It runs once to do the slow, heavy work of calling the get_real_travel_time function for every possible pair of locations. It saves its output—a complete travel time matrix and a list of locations—into time_matrix.json, enabling the main simulation to start instantly.

Simulation Engine Files:
dynamic_solver.py

What it does: This is the "quick-thinking" brain of the simulation. It contains the solve_for_best_insertion function. This is not a full VRP solver; it's a lightweight, fast heuristic that takes a set of current routes and one new order, and instantly calculates the most efficient way to insert that order while respecting all business constraints (max stops, max route time).

run_dynamic_simulation.py

What it does: This is the main script and heart of the project. It orchestrates the entire simulation. It loads the master time matrix, initializes the vehicles, runs the clock, generates random new orders, and uses the dynamic_solver to make real-time assignment decisions. Its output is the detailed text log that shows the entire day's operations.