import mysql.connector
import pandas as pd
import numpy as np
import pickle
import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX

MODEL_FILENAME = "inventory_forecast_models.pkl"

def fetch_data_from_db():
    print("🔌 Connecting to MySQL Database...")
    # Linking directly to your active inventory_system database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aps@JC-857079N",  # Keep your real password here!
        database="inventory_system"      # <-- MUST be exactly inventory_system
    )
    
    # Prefer the canonical `stock_transactions` table when available.
    # If it doesn't exist, fall back to the `historical_sales` table (CSV importer).
    try:
        query = """
        SELECT 
            transaction_date as date,
            product_id,
            quantity_changed,
            transaction_type
        FROM stock_transactions;
        """
        df = pd.read_sql(query, conn)
    except Exception:
        # Fallback: try to read the table created by `upload_to_db.py` (historical_sales)
        try:
            fallback_q = "SELECT date, product_id, quantity_sold FROM historical_sales"
            tmp = pd.read_sql(fallback_q, conn)
            # Normalize to the expected schema: transaction_date/date, quantity_changed, transaction_type
            tmp = tmp.rename(columns={'quantity_sold': 'quantity_changed'})
            # Treat all historical rows as sales events
            tmp['transaction_type'] = 'SALES'
            # quantity_changed should reflect removals for sales (negative), but prepare_features uses abs()
            tmp['quantity_changed'] = -tmp['quantity_changed']
            df = tmp[['date', 'product_id', 'quantity_changed', 'transaction_type']]
        except Exception as e:
            conn.close()
            raise
    conn.close()
    print(f"✅ Successfully fetched {len(df)} transaction records!")
    return df

def prepare_time_series_models(df):
    print("📊 Building time-series forecasting models for each product...")
    df['date'] = pd.to_datetime(df['date'])
    df['sales_volume'] = df.apply(
        lambda row: abs(row['quantity_changed']) if row['transaction_type'] in ['SALES', 'RESTOCK_OUT'] else 0,
        axis=1
    )
    df = df[df['transaction_type'].isin(['SALES', 'RESTOCK_OUT'])]

    product_models = {}
    for product_id, group in df.groupby('product_id'):
        series = group.groupby('date')['sales_volume'].sum().sort_index()
        series = series.asfreq('D', fill_value=0)

        if len(series) < 30:
            print(f"⚠️ Skipping product {product_id}: not enough data for a reliable time-series model.")
            product_models[int(product_id)] = None
            continue

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            model = SARIMAX(
                series,
                order=(1, 1, 1),
                seasonal_order=(1, 0, 1, 7),
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            result = model.fit(disp=False)
            product_models[int(product_id)] = result
            print(f"✅ Trained time-series model for product {product_id}")

    return product_models

def train_forecasting_model():
    raw_data = fetch_data_from_db()
    model_dict = prepare_time_series_models(raw_data)

    with open(MODEL_FILENAME, 'wb') as file:
        pickle.dump(model_dict, file)

    print(f"\n💾 Time-series models saved to '{MODEL_FILENAME}'")


if __name__ == "__main__":
    train_forecasting_model()