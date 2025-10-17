import pandas as pd
import random
import os

def generate_time_windows(demand):
    """
    Generates a realistic (earliest_time, latest_time) tuple in minutes
    from the start of the day (e.g., 9:00 AM = 0 minutes), based on demand.

    Args:
        demand (int): The average daily demand for a location.

    Returns:
        tuple: A tuple containing the earliest and latest delivery time in minutes.
    """
    # High Demand (> 20 orders/day) -> Prime lunch or dinner slots
    if demand > 20:
        # Randomly assign to a 3-hour lunch or dinner window
        if random.choice([True, False]):
            # Lunch rush: 12:00 PM (180 min) to 3:00 PM (360 min)
            return (180, 360)
        else:
            # Dinner rush: 6:00 PM (540 min) to 9:00 PM (720 min)
            return (540, 720)
    # Medium Demand (6-20 orders/day) -> Broader afternoon slot
    elif demand > 5:
        # Afternoon: 1:00 PM (240 min) to 5:00 PM (480 min)
        return (240, 480)
    # Low Demand (<= 5 orders/day) -> Flexible all-day window
    else:
        # Flexible: 10:00 AM (60 min) to 7:00 PM (600 min)
        return (60, 600)

def process_demand_data(input_filename, output_filename):
    """
    Reads a CSV, adds time window columns based on demand,
    and saves it to a new CSV file.
    """
    try:
        # Read the original data file
        df = pd.read_csv(input_filename)
        print(f"Successfully read '{input_filename}'.")

        # --- Generate Time Windows ---
        # Apply the logic to the demand column to create a temporary tuple column
        df['time_window'] = df['average_daily_demand'].apply(generate_time_windows)

        # Split the tuple into two separate columns for earliest and latest times
        df['earliest_time'] = df['time_window'].apply(lambda x: x[0])
        df['latest_time'] = df['time_window'].apply(lambda x: x[1])

        # Remove the temporary 'time_window' column
        df.drop(columns=['time_window'], inplace=True)
        
        # Ensure the column order is logical
        df = df[['Subzone', 'average_daily_demand', 'earliest_time', 'latest_time']]

        # --- Save the new file ---
        df.to_csv(output_filename, index=False)
        print(f"Successfully created '{output_filename}' with time windows.")
        print("\n--- Sample of the new data ---")
        print(df.head())
        print("----------------------------")


    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
        print("Please make sure the file is in the same directory as this script.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Define the input and output filenames
    # Make sure your original CSV file is named 'subzone_demand.csv'
    # or change the name below.
    input_csv = 'subzone_demand.csv'
    output_csv = 'subzone_demand_with_time.csv'
    
    # Create a dummy file for demonstration if it doesn't exist
    if not os.path.exists(input_csv):
        print(f"'{input_csv}' not found. Creating a sample file for demonstration.")
        sample_data = {
            'Subzone': ['Chittaranjan Park', 'DLF Phase 1', 'Greater Kailash 2 (GK2)', 'Sector 135', 'Sector 4', 'Shahdara', 'Sikandarpur', 'Vasant Kunj'],
            'average_daily_demand': [1, 24, 48, 16, 43, 5, 1, 7]
        }
        pd.DataFrame(sample_data).to_csv(input_csv, index=False)
        print("Sample file created.")

    # Run the processing function
    process_demand_data(input_csv, output_csv)
