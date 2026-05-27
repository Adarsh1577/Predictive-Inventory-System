import pandas as pd
import urllib.parse  # 👈 Add this import at the top
from sqlalchemy import create_engine

def upload_data_to_mysql():
    try:
        df = pd.read_csv("historical_sales.csv")
    except FileNotFoundError:
        print("❌ Error: historical_sales.csv not found!")
        return

    db_ready_df = df[['Date', 'Product_ID', 'Quantity_Sold']].copy()
    db_ready_df.rename(columns={
        'Date': 'date',
        'Product_ID': 'product_id',
        'Quantity_Sold': 'quantity_sold'
    }, inplace=True)

    db_user = "root"
    # 👈 Wrap your password string inside urllib.parse.quote_plus()
    raw_pass = "Aps@JC-857079N"  
    db_pass = urllib.parse.quote_plus(raw_pass)
    
    db_host = "localhost"
    db_port = "3306"
    db_name = "inventory_system"
    
    conn_str = f"mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    try:
        engine = create_engine(conn_str)
        print("🔗 Connecting to MySQL Database server...")
        
        db_ready_df.to_sql(
            name='historical_sales', 
            con=engine, 
            if_exists='append', 
            index=False
        )
        print("🚀 Success! All daily transaction rows migrated securely into MySQL.")
        
    except Exception as e:
        print(f"❌ Connection or upload failed: {e}")

if __name__ == "__main__":
    upload_data_to_mysql()