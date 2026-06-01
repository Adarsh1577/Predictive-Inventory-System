from fastapi import FastAPI, HTTPException
import mysql.connector
import pandas as pd
import datetime
import pickle
import numpy as np

FORECAST_HORIZON = 7

app = FastAPI(
    title="Smart Alert Inventory Forecasting API",
    description=(
        "REST API with multi-day autoregressive demand forecasting, "
        "7-day safety-margin procurement alerts, and depletion analytics."
    ),
    version="2.0.0",
)

MODEL_FILENAME = "inventory_forecast_models.pkl"


def load_forecast_models():
    try:
        with open(MODEL_FILENAME, "rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"Forecast model file '{MODEL_FILENAME}' not found. Please train the model first.",
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to load forecast models: {err}")


def autoregressive_forecast(model_result, horizon=FORECAST_HORIZON):
    """
    Rolling 1-step-ahead loop: predict Day N, append that value to the series,
    then use the updated state (lag) to predict Day N+1 through Day 7.
    """
    if model_result is None:
        return [0] * horizon

    daily_forecast = []
    current = model_result

    try:
        for _ in range(horizon):
            fc = current.get_forecast(steps=1)
            pred_series = fc.predicted_mean
            pred_val = float(pred_series.iloc[-1]) if hasattr(pred_series, "iloc") else float(pred_series[-1])
            pred_int = int(max(0, round(pred_val)))
            daily_forecast.append(pred_int)
            current = current.append(endog=[pred_val], refit=False)
    except Exception:
        while len(daily_forecast) < horizon:
            daily_forecast.append(0)

    return daily_forecast


def build_forecast_calendar(start_date, horizon=FORECAST_HORIZON):
    """Return parallel lists of ISO dates and human-readable day labels."""
    dates = [start_date + datetime.timedelta(days=i) for i in range(horizon)]
    return [d.isoformat() for d in dates], [f"Day {i + 1} ({d.strftime('%b %d')})" for i, d in enumerate(dates)]


def evaluate_7day_safety(current_stock, reorder_level, daily_forecast, start_date):
    """
    7-day critical safety margin:
      required_buffer = sum(7-day demand) + reorder_level
    Alert when stock cannot cover the full horizon plus safety buffer,
    or when cumulative demand depletes stock within the window.
    """
    forecast_arr = np.array(daily_forecast, dtype=float)
    cumulative = np.cumsum(forecast_arr)
    predicted_7_day_total = int(cumulative[-1]) if len(cumulative) else 0
    safety_buffer_required = predicted_7_day_total + int(reorder_level)
    critical_shortfall = max(0, int(safety_buffer_required - current_stock))

    depletion_day = next(
        (i + 1 for i, total in enumerate(cumulative) if total >= current_stock),
        None,
    )

    covers_7day_margin = current_stock >= safety_buffer_required
    low_stock = current_stock <= reorder_level
    procurement_alert = not covers_7day_margin or depletion_day is not None

    if depletion_day is not None:
        depletion_date = start_date + datetime.timedelta(days=depletion_day - 1)
        depletion_date_str = str(depletion_date)
        depletion_in_days = depletion_day
    else:
        depletion_date_str = None
        depletion_in_days = None

    if procurement_alert:
        recommended_order_quantity = critical_shortfall
    elif low_stock:
        recommended_order_quantity = max(0, int(reorder_level - current_stock))
    else:
        recommended_order_quantity = 0

    return {
        "predicted_7_day_total": predicted_7_day_total,
        "safety_buffer_required": safety_buffer_required,
        "critical_shortfall": critical_shortfall,
        "covers_7day_margin": covers_7day_margin,
        "low_stock": low_stock,
        "depletion_date": depletion_date_str,
        "depletion_in_days": depletion_in_days,
        "procurement_alert": procurement_alert,
        "recommended_order_quantity": recommended_order_quantity,
    }


def resolve_status(current_stock, reorder_level, safety_eval):
    if safety_eval["procurement_alert"]:
        if safety_eval["depletion_in_days"] is not None and safety_eval["depletion_in_days"] <= 3:
            return "🚨 CRITICAL — 7-DAY MARGIN"
        return "🚨 PROCUREMENT ALERT"
    if safety_eval.get("low_stock") or current_stock <= reorder_level:
        return "⚠️ LOW STOCK"
    return "✅ HEALTHY"


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "Welcome to the Multi-Day Autoregressive Inventory Forecasting API!",
        "forecast_horizon_days": FORECAST_HORIZON,
        "docs_url": "http://127.0.0.1:8001/docs",
    }


@app.get("/api/v1/procurement-alerts")
def procurement_alerts():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Aps@JC-857079N",
            database="inventory_system",
        )
        cursor = conn.cursor(dictionary=True)
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Connection Failed: {err}")

    query = """
    SELECT alert_id, product_id, product_name, alert_generated, depletion_date, days_to_depletion,
           predicted_7_day_total, recommended_order_qty, status, created_at
    FROM procurement_alerts
    ORDER BY alert_generated DESC, days_to_depletion ASC;
    """
    cursor.execute(query)
    alerts = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "total_alerts": len(alerts),
        "alerts": alerts,
    }


@app.get("/api/v1/check-inventory")
def check_inventory_alerts():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Aps@JC-857079N",
            database="inventory_system",
        )
        cursor = conn.cursor(dictionary=True)
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database Connection Failed: {err}")

    models = load_forecast_models()

    query_stock = """
    SELECT p.product_id, p.product_name, i.current_stock, i.reorder_level
    FROM products p
    JOIN inventory i ON p.product_id = i.product_id;
    """
    cursor.execute(query_stock)
    products_list = cursor.fetchall()

    horizon_start = datetime.date.today() + datetime.timedelta(days=1)
    horizon_end = horizon_start + datetime.timedelta(days=FORECAST_HORIZON - 1)
    forecast_dates, forecast_day_labels = build_forecast_calendar(horizon_start)

    dashboard_results = []

    for prod in products_list:
        pid = prod["product_id"]
        pname = prod["product_name"]
        current_stock = prod["current_stock"]
        reorder_level = prod["reorder_level"]

        model = models.get(pid)
        daily_forecast = autoregressive_forecast(model, horizon=FORECAST_HORIZON)

        safety_eval = evaluate_7day_safety(
            current_stock, reorder_level, daily_forecast, horizon_start
        )
        status = resolve_status(current_stock, reorder_level, safety_eval)

        dashboard_results.append(
            {
                "product_id": pid,
                "product_name": pname,
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "predicted_demand_tomorrow": daily_forecast[0] if daily_forecast else 0,
                "predicted_7_day_total": safety_eval["predicted_7_day_total"],
                "safety_buffer_required": safety_eval["safety_buffer_required"],
                "critical_shortfall": safety_eval["critical_shortfall"],
                "covers_7day_margin": safety_eval["covers_7day_margin"],
                "low_stock": safety_eval["low_stock"],
                "forecast_next_7_days": daily_forecast,
                "forecast_dates": forecast_dates,
                "forecast_day_labels": forecast_day_labels,
                "status": status,
                "action_required": safety_eval["procurement_alert"] or safety_eval["low_stock"],
                "procurement_alert": safety_eval["procurement_alert"],
                "recommended_order_quantity": safety_eval["recommended_order_quantity"],
                "depletion_date": safety_eval["depletion_date"],
                "depletion_in_days": safety_eval["depletion_in_days"],
            }
        )

    cursor.close()
    conn.close()

    return {
        "forecast_horizon_days": FORECAST_HORIZON,
        "forecast_horizon_start": str(horizon_start),
        "forecast_horizon_end": str(horizon_end),
        "forecast_dates": forecast_dates,
        "forecast_day_labels": forecast_day_labels,
        "total_items_checked": len(dashboard_results),
        "inventory_report": dashboard_results,
    }
