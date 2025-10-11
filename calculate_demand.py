import pandas as pd

# This script calculates the average daily demand for each sub-zone.

INPUT_FILE = 'order_history_kaggle_data.csv'
OUTPUT_FILE = 'subzone_demand.csv'

try:
    # Load the original dataset
    df_orders = pd.read_csv(INPUT_FILE)
    print("✅ Successfully loaded 'order_history_kaggle_data.csv'.")

    # --- Step 1: Data Cleaning and Preparation ---
    # Convert 'Order Placed At' to a proper datetime format.
    df_orders['order_datetime'] = pd.to_datetime(df_orders['Order Placed At'], format='%I:%M %p, %B %d %Y')
    df_orders['order_date'] = df_orders['order_datetime'].dt.date
    df_orders.dropna(subset=['Subzone'], inplace=True)
    df_orders['Subzone'] = df_orders['Subzone'].str.strip()

    # --- Step 2: Aggregate Orders by Day and Subzone ---
    daily_demand = df_orders.groupby(['order_date', 'Subzone'])['Order ID'].count().reset_index()
    daily_demand.rename(columns={'Order ID': 'order_count'}, inplace=True)

    # --- Step 3: Calculate Average Daily Demand ---
    avg_daily_demand = daily_demand.groupby('Subzone')['order_count'].mean().round().reset_index()
    avg_daily_demand.rename(columns={'order_count': 'average_daily_demand'}, inplace=True)
    
    # Demand must be at least 1 for the optimization model to make sense.
    avg_daily_demand['average_daily_demand'] = avg_daily_demand['average_daily_demand'].clip(lower=1).astype(int)

    print("\nCalculated average daily demand for each sub-zone:")
    print(avg_daily_demand)

    # --- Step 4: Save the Result ---
    avg_daily_demand.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Successfully saved the demand forecast to '{OUTPUT_FILE}'.")

except FileNotFoundError:
    print(f"❌ Error: Could not find '{INPUT_FILE}'. Make sure it's in the same folder as this script.")
except Exception as e:
    print(f"An error occurred: {e}")