"""
Background 7-day autoregressive inventory evaluation.
Persists CRITICAL / WARNING / HEALTHY alerts to MySQL (aligned with main.py).
"""
import datetime
import pickle

import mysql.connector
import numpy as np

FORECAST_HORIZON = 7
MODEL_FILENAME = "inventory_forecast_models.pkl"


def load_forecast_models():
    print("🧠 Loading trained time-series forecasting models...")
    with open(MODEL_FILENAME, "rb") as file:
        return pickle.load(file)


def autoregressive_forecast(model_result, horizon=FORECAST_HORIZON):
    """Rolling 1-step loop: predict Day N, append as lag, roll forward to Day 7."""
    if model_result is None:
        return [0] * horizon

    daily_forecast = []
    current = model_result

    try:
        for _ in range(horizon):
            fc = current.get_forecast(steps=1)
            pred_series = fc.predicted_mean
            pred_val = (
                float(pred_series.iloc[-1])
                if hasattr(pred_series, "iloc")
                else float(pred_series[-1])
            )
            pred_int = int(max(0, round(pred_val)))
            daily_forecast.append(pred_int)
            current = current.append(endog=[pred_val], refit=False)
    except Exception:
        while len(daily_forecast) < horizon:
            daily_forecast.append(0)

    return daily_forecast


def evaluate_7day_lookahead(current_stock, reorder_level, daily_forecast, start_date):
    """7-day window metrics shared with main.py safety evaluation."""
    forecast_arr = np.array(daily_forecast, dtype=float)
    cumulative = np.cumsum(forecast_arr)
    predicted_7_day_total = int(cumulative[-1]) if len(cumulative) else 0
    projected_stock_after_demand = int(current_stock - predicted_7_day_total)

    depletion_day = next(
        (i + 1 for i, total in enumerate(cumulative) if total >= current_stock),
        None,
    )

    if depletion_day is not None:
        depletion_date = start_date + datetime.timedelta(days=depletion_day - 1)
        days_to_depletion = depletion_day
    else:
        depletion_date = start_date + datetime.timedelta(days=FORECAST_HORIZON - 1)
        days_to_depletion = FORECAST_HORIZON + 1

    safety_buffer_required = predicted_7_day_total + int(reorder_level)
    critical_shortfall = max(0, int(safety_buffer_required - current_stock))

    return {
        "predicted_7_day_total": predicted_7_day_total,
        "projected_stock_after_demand": projected_stock_after_demand,
        "depletion_date": depletion_date,
        "days_to_depletion": days_to_depletion,
        "critical_shortfall": critical_shortfall,
        "safety_buffer_required": safety_buffer_required,
    }


def classify_stock_alert(current_stock, reorder_level, predicted_7_day_total):
    """
    CRITICAL — on-hand stock at or below reorder level.
    WARNING — after 7-day demand, projected stock at or below reorder level.
    HEALTHY — sufficient stock through the 7-day horizon.
    """
    if current_stock <= reorder_level:
        return "CRITICAL"
    if current_stock - predicted_7_day_total <= reorder_level:
        return "WARNING"
    return "HEALTHY"


def recommended_order_quantity(status, current_stock, reorder_level, metrics):
    if status == "CRITICAL":
        return max(0, int(reorder_level - current_stock), metrics["critical_shortfall"])
    if status == "WARNING":
        return metrics["critical_shortfall"]
    return 0


def upsert_procurement_alert(cursor, alert_data):
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
            product_name = VALUES(product_name),
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
            alert_data["status"],
        ),
    )


def check_inventory_and_alert():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aps@JC-857079N",
        database="inventory_system",
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

    horizon_start = datetime.date.today() + datetime.timedelta(days=1)
    alert_generated = datetime.date.today()

    print(
        f"\n🔮 7-day autoregressive look-ahead for {len(products_list)} products "
        f"(horizon starts {horizon_start})\n"
    )

    counts = {"CRITICAL": 0, "WARNING": 0, "HEALTHY": 0}

    for prod in products_list:
        pid = prod["product_id"]
        pname = prod["product_name"]
        current_stock = int(prod["current_stock"])
        reorder_level = int(prod["reorder_level"])

        model = models.get(pid)
        daily_forecast = autoregressive_forecast(model, horizon=FORECAST_HORIZON)

        metrics = evaluate_7day_lookahead(
            current_stock, reorder_level, daily_forecast, horizon_start
        )
        status = classify_stock_alert(
            current_stock, reorder_level, metrics["predicted_7_day_total"]
        )
        recommended_qty = recommended_order_quantity(
            status, current_stock, reorder_level, metrics
        )

        alert_data = {
            "product_id": pid,
            "product_name": pname,
            "alert_generated": alert_generated,
            "depletion_date": metrics["depletion_date"],
            "days_to_depletion": metrics["days_to_depletion"],
            "predicted_7_day_total": metrics["predicted_7_day_total"],
            "recommended_order_qty": recommended_qty,
            "status": status,
        }
        upsert_procurement_alert(cursor, alert_data)
        counts[status] += 1

        icon = {"CRITICAL": "🚨", "WARNING": "⚠️", "HEALTHY": "✅"}[status]
        print(
            f"{icon} {pname}: {status} | stock={current_stock} | "
            f"7-day demand={metrics['predicted_7_day_total']} | "
            f"projected after demand={metrics['projected_stock_after_demand']} | "
            f"reorder={reorder_level} | recommended order={recommended_qty}"
        )

    conn.commit()
    cursor.close()
    conn.close()

    print(
        f"\n🔌 Evaluation complete — CRITICAL: {counts['CRITICAL']}, "
        f"WARNING: {counts['WARNING']}, HEALTHY: {counts['HEALTHY']}\n"
    )


if __name__ == "__main__":
    try:
        check_inventory_and_alert()
    except FileNotFoundError:
        print(f"❌ Model file '{MODEL_FILENAME}' not found. Run: py train_model.py")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
