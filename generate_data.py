import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_sales():
    # Set seed so we always get the exact same random numbers
    np.random.seed(42)
    
    # 1. Setup Timeline: Exactly past 2 years (730 days) up to today
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # 2. Setup the item baseline metrics
    products = [
        {"id": 101, "name": "Wireless Headphones", "base_sales": 25},
        {"id": 102, "name": "Mechanical Keyboard", "base_sales": 15},
        {"id": 103, "name": "Ergonomic Gaming Mouse", "base_sales": 40}
    ]
    
    all_records = []
    
    # 3. Simulate daily enterprise transactions
    for current_date in date_range:
        day_of_week = current_date.weekday()  # 5 = Saturday, 6 = Sunday
        month = current_date.month
        
        for prod in products:
            demand = prod["base_sales"]
            
            # Pattern A: Weekend shopping surges
            if day_of_week >= 5:
                demand *= np.random.uniform(1.3, 1.6)
                
            # Pattern B: Peak Q4 holiday shopping spikes (Nov & Dec)
            if month in [11, 12]:
                demand *= np.random.uniform(1.4, 1.8)
                
            # Pattern C: Inject realistic daily statistical fluctuation
            noise = np.random.normal(0, 3)
            final_sales = max(0, int(demand + noise))
            
            all_records.append({
                "Date": current_date.strftime('%Y-%m-%d'),
                "Product_ID": prod["id"],
                "Product_Name": prod["name"],
                "Quantity_Sold": final_sales
            })
            
    # Convert list of dictionaries cleanly into a Pandas DataFrame
    df = pd.DataFrame(all_records)
    
    # Save a physical file to our root folder directory
    df.to_csv("historical_sales.csv", index=False)
    print(f"🎉 Dataset generated perfectly! {len(df)} daily sales records saved to historical_sales.csv")
    return df

if __name__ == "__main__":
    generate_synthetic_sales()