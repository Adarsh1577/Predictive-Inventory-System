import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Smart Alert Inventory Dashboard",
    page_icon="📦",
    layout="wide",
)

st.title("📦 Smart Alert Inventory Forecasting System")
st.markdown(
    "### Multi-Day Autoregressive Demand Forecasting & 7-Day Safety Margin Analytics"
)
st.caption(
    "Rolling 7-day forecasts: each day’s prediction feeds the next as a lag feature. "
    "Procurement alerts use cumulative demand plus reorder-level safety buffers."
)

st.markdown("---")

FASTAPI_URL = "http://127.0.0.1:8001/api/v1/check-inventory"
BACKEND_DOCS_URL = "http://127.0.0.1:8001/docs"


def build_trend_dataframe(report_list, forecast_dates, forecast_day_labels):
    """Long-format rows for per-product 7-day trend charts."""
    rows = []
    for item in report_list:
        daily = item.get("forecast_next_7_days") or []
        dates = item.get("forecast_dates") or forecast_dates
        labels = item.get("forecast_day_labels") or forecast_day_labels
        for i, demand in enumerate(daily):
            rows.append(
                {
                    "product_name": item["product_name"],
                    "product_id": item["product_id"],
                    "forecast_date": dates[i] if i < len(dates) else labels[i],
                    "day_label": labels[i] if i < len(labels) else f"Day {i + 1}",
                    "predicted_demand": demand,
                    "day_index": i + 1,
                }
            )
    return pd.DataFrame(rows)


try:
    with st.spinner("🔄 Running 7-day autoregressive forecast pipeline..."):
        response = requests.get(FASTAPI_URL, timeout=30)

    if response.status_code != 200:
        st.error(
            f"❌ FastAPI returned status {response.status_code}. "
            "Ensure the backend is running on port 8001."
        )
        st.stop()

    data = response.json()
    report_list = data.get("inventory_report", [])
    forecast_dates = data.get("forecast_dates", [])
    forecast_day_labels = data.get("forecast_day_labels", [])
    horizon_start = data.get("forecast_horizon_start", "—")
    horizon_end = data.get("forecast_horizon_end", "—")
    horizon_days = data.get("forecast_horizon_days", 7)

    if not report_list:
        st.warning("No inventory records returned from the API.")
        st.stop()

    df = pd.DataFrame(report_list)
    trend_df = build_trend_dataframe(report_list, forecast_dates, forecast_day_labels)

    total_items = len(df)
    procurement_alerts = int(df["procurement_alert"].sum()) if "procurement_alert" in df.columns else 0
    low_stock_alerts = len(df[df["status"].str.contains("LOW STOCK", na=False)])
    healthy_items = len(df[df["status"] == "✅ HEALTHY"])
    total_7day_demand = int(df["predicted_7_day_total"].sum()) if "predicted_7_day_total" in df.columns else 0
    critical_margin = len(df[df["status"].str.contains("CRITICAL", na=False)])

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Tracked Items", total_items)
    with col2:
        st.metric(
            "📊 Portfolio 7-Day Demand",
            f"{total_7day_demand:,}",
            help="Sum of autoregressive 7-day forecasts across all products",
        )
    with col3:
        st.metric(
            "🛒 Procurement Alerts",
            procurement_alerts,
            delta=f"{procurement_alerts} active" if procurement_alerts else "none",
            delta_color="inverse",
        )
    with col4:
        st.metric(
            "🚨 Critical 7-Day Margin",
            critical_margin,
            delta="≤3 days to depletion" if critical_margin else "clear",
            delta_color="inverse",
        )
    with col5:
        st.metric("✅ Healthy Products", healthy_items)

    st.info(
        f"**Forecast window:** {horizon_start} → {horizon_end} "
        f"({horizon_days}-day autoregressive horizon)"
    )

    st.markdown("---")
    st.markdown(f"#### API documentation: [{BACKEND_DOCS_URL}]({BACKEND_DOCS_URL})")

    st.subheader("📋 7-Day Inventory & Safety Margin Report")
    display_columns = [
        "product_id",
        "product_name",
        "current_stock",
        "reorder_level",
        "predicted_7_day_total",
        "safety_buffer_required",
        "critical_shortfall",
        "covers_7day_margin",
        "forecast_next_7_days",
        "depletion_date",
        "depletion_in_days",
        "recommended_order_quantity",
        "status",
    ]
    display_df = df[[c for c in display_columns if c in df.columns]]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    urgent_df = df[df["action_required"] == True].sort_values(  # noqa: E712
        by="depletion_in_days", na_position="last"
    )
    if not urgent_df.empty:
        st.markdown("---")
        st.subheader("🚨 Urgent Procurement — 7-Day Safety Breach")
        st.dataframe(
            urgent_df[
                [
                    "product_name",
                    "current_stock",
                    "predicted_7_day_total",
                    "safety_buffer_required",
                    "critical_shortfall",
                    "depletion_date",
                    "depletion_in_days",
                    "recommended_order_quantity",
                    "status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("📈 7-Day Demand Trend (Autoregressive Roll-Forward)")

    chart_col1, chart_col2 = st.columns([1, 2])

    with chart_col1:
        product_names = sorted(df["product_name"].unique().tolist())
        selected_product = st.selectbox(
            "Select product for trend view",
            product_names,
            index=0,
        )
        product_row = df[df["product_name"] == selected_product].iloc[0]
        st.metric(
            label=f"7-Day Demand — {selected_product}",
            value=f"{int(product_row['predicted_7_day_total']):,} units",
            delta=(
                f"Shortfall {int(product_row['critical_shortfall']):,}"
                if product_row.get("critical_shortfall", 0) > 0
                else "Margin OK"
            ),
            delta_color="inverse" if product_row.get("critical_shortfall", 0) > 0 else "normal",
        )
        st.metric("Current Stock", int(product_row["current_stock"]))
        st.metric("Safety Buffer Required", int(product_row["safety_buffer_required"]))

    with chart_col2:
        product_trend = trend_df[trend_df["product_name"] == selected_product].copy()
        if not product_trend.empty:
            line_df = product_trend.set_index("forecast_date")[["predicted_demand"]]
            line_df.index = pd.to_datetime(line_df.index)
            line_df.columns = ["Predicted daily demand"]
            st.line_chart(line_df, height=380)

            avg_daily = product_row["predicted_7_day_total"] / max(horizon_days, 1)
            st.caption(
                f"Solid line: rolling autoregressive daily forecast. "
                f"Average ~{avg_daily:.1f} units/day over {horizon_days} days."
            )

    st.markdown("#### Portfolio-wide 7-day demand curve")
    if not trend_df.empty:
        portfolio_daily = (
            trend_df.groupby("forecast_date", as_index=False)["predicted_demand"]
            .sum()
            .set_index("forecast_date")
        )
        portfolio_daily.index = pd.to_datetime(portfolio_daily.index)
        portfolio_daily.columns = ["Total predicted demand (all products)"]
        st.line_chart(portfolio_daily, height=320)

    st.markdown("---")
    st.subheader("📊 Stock vs 7-Day Cumulative Demand")
    comparison = df.set_index("product_name")[
        ["current_stock", "predicted_7_day_total", "safety_buffer_required"]
    ].rename(
        columns={
            "current_stock": "Current stock",
            "predicted_7_day_total": "7-day demand",
            "safety_buffer_required": "Required buffer (demand + reorder)",
        }
    )
    st.bar_chart(comparison, height=360)

except requests.exceptions.ConnectionError:
    st.error(
        "🔌 Cannot reach the FastAPI backend. Start it with:\n\n"
        "`py -m uvicorn main:app --host 127.0.0.1 --port 8001`"
    )
except requests.exceptions.Timeout:
    st.error("⏱️ Request timed out. The forecasting loop may be slow on first run.")
except Exception as exc:
    st.error(f"Unexpected error: {exc}")
