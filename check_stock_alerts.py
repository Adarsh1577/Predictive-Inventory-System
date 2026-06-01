import mysql.connector
import pandas as pd
import datetime
import pickle
import numpy as np

MODEL_FILENAME = "inventory_forecast_models.pkl"


def load_forecast_models():
    print("🧠 Loading trained time-series forecasting models...")
    with open(MODEL_FILENAME, "rb") as file:
        return pickle.load(file)


def calculate_depletion(current_stock, reorder_level, daily_forecast, start_date):
    cumulative = np.cumsum(daily_forecast)
    depletion_day = next((i + 1 for i, total in enumerate(cumulative) if total >= current_stock), None)

    if depletion_day is None:
        return None

    depletion_date = start_date + datetime.timedelta(days=depletion_day - 1)
    recommended_order_qty = max(0, int(cumulative[-1] - current_stock + reorder_level))

    return {
        "depletion_date": depletion_date,
        "days_to_depletion": depletion_day,
        "predicted_7_day_total": int(cumulative[-1]),
        "recommended_order_qty": recommended_order_qty
    }


def create_procurement_alert(cursor, alert_data):
    cursor.execute(
        """
        INSERT INTO procurement_alerts (
            product_id,
            product_name,
            alert_generated,
            depletion_date,
            days_to_depletion,
            predicted_7_day_total,
            recommended_order_qty,
            status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            alert_generated = VALUES(alert_generated),
            days_to_depletion = VALUES(days_to_depletion),
            predicted_7_day_total = VALUES(predicted_7_day_total),
            recommended_order_qty = VALUES(recommended_order_qty),
            status = VALUES(status)
        """,
        (
            alert_data["product_id"],
            alert_data["product_name"],
            alert_data["alert_generated"],
            alert_data["depletion_date"],
            alert_data["days_to_depletion"],
            alert_data["predicted_7_day_total"],
            alert_data["recommended_order_qty"],
            alert_data["status"]
        )
    )


def check_inventory_and_alert():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aps@JC-857079N",
        database="inventory_system"
    )
    cursor = conn.cursor(dictionary=True)
    models = load_forecast_models()

    query_stock = """
    SELECT p.product_id, p.product_name, i.current_stock, i.reorder_level
    FROM products p
    JOIN inventory i ON p.product_id = i.product_id;
    """
    cursor.execute(query_stock)
    products_list = cursor.fetchall()

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    print(f"\n🔮 Checking procurement risk for {len(products_list)} products on {tomorrow}\n")

    for prod in products_list:
        pid = prod['product_id']
        pname = prod['product_name']
        current_stock = prod['current_stock']
        reorder_level = prod['reorder_level']

        model = models.get(pid)
        if model is None:
            daily_forecast = np.zeros(7, dtype=int)
        else:
            try:
                forecast = model.get_forecast(steps=7)
                daily_forecast = np.array([int(max(0, round(x))) for x in forecast.predicted_mean])
            except Exception:
                daily_forecast = np.zeros(7, dtype=int)

        depletion = calculate_depletion(current_stock, reorder_level, daily_forecast, tomorrow)

        if depletion is not None:
            alert_data = {
                "product_id": pid,
                "product_name": pname,
                "alert_generated": tomorrow,
                "depletion_date": depletion["depletion_date"],
                "days_to_depletion": depletion["days_to_depletion"],
                "predicted_7_day_total": depletion["predicted_7_day_total"],
                "recommended_order_qty": depletion["recommended_order_qty"],
                "status": "OPEN"
            }
            create_procurement_alert(cursor, alert_data)
            print(f"🚨 Procurement alert created for {pname}: depletion in {depletion['days_to_depletion']} days ({depletion['depletion_date']})")
        else:
            print(f"✅ {pname} does not require procurement within 7 days.")

    conn.commit()
    cursor.close()
    conn.close()
    print("\n🔌 Procurement risk assessment complete.")


if __name__ == "__main__":
    try:
        check_inventory_and_alert()
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

        