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

    from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

    db_user = DB_USER
    raw_pass = DB_PASSWORD
    db_pass = urllib.parse.quote_plus(raw_pass)
    
    db_host = DB_HOST
    db_port = str(DB_PORT)
    db_name = DB_NAME
    
    conn_str = f"mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    try:
        engine = create_engine(conn_str)
        print("Connecting to MySQL Database server...")
        
        db_ready_df.to_sql(
            name='historical_sales', 
            con=engine, 
            if_exists='append', 
            index=False
        )
        print("Success! All daily transaction rows migrated securely into MySQL.")
        
    except Exception as e:
        print(f"❌ Connection or upload failed: {e}")

if __name__ == "__main__":
    upload_data_to_mysql()