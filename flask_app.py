"""
flask_app.py
============
Flask Full-Stack Web Application for SDG E-Commerce Analysis.
Serves:
- HTML/CSS Frontend from templates/index.html and static/
- JSON REST APIs connecting SQLite and MongoDB Atlas
- Fallback/Alternative server to FastAPI
"""

import os
import sys
import time
import json
from typing import Optional
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

from data_cleaning import get_or_create_cleaned_data
from database import (
    DEFAULT_DB_PATH,
    get_top_5_products_by_revenue,
    get_monthly_revenue_summary,
    get_joined_order_details,
    get_products_exceeding_average_sales,
    get_category_performance,
    execute_custom_sql,
    get_mongo_status,
    aggregate_sdg_by_category,
    aggregate_logistics_footprint,
    aggregate_recommendations_by_sdg,
    execute_custom_mongo_pipeline,
    reset_mongo_connection,
    mask_mongo_uri
)
from analysis import (
    get_overall_kpis,
    get_monthly_trends,
    get_top_products,
    get_cancellation_analysis,
    get_sdg12_metrics,
    get_sdg9_metrics,
    sync_analytics_to_mongodb
)

app = Flask(__name__, template_folder="templates", static_folder="static")

_DF_CACHE = None


def get_cached_df():
    global _DF_CACHE
    if _DF_CACHE is None:
        _DF_CACHE = get_or_create_cleaned_data()
    return _DF_CACHE


def apply_filters(df, country=None, category=None, status=None):
    filtered = df.copy()
    if country and country != "All":
        filtered = filtered[filtered["Country"] == country]
    if category and category != "All":
        filtered = filtered[filtered["Category"] == category]
    if status == "fulfilled":
        filtered = filtered[~filtered["IsCancelled"]]
    elif status == "cancelled":
        filtered = filtered[filtered["IsCancelled"]]
    return filtered


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    mongo_stat = get_mongo_status()
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    is_atlas = "mongodb+srv://" in uri or "mongodb.net" in uri
    return jsonify({
        "status": "online",
        "sqlite": {"connected": os.path.exists(DEFAULT_DB_PATH), "database": "data/ecommerce.db"},
        "mongodb": {
            "connected": mongo_stat["connected"],
            "mode": mongo_stat["mode"],
            "is_atlas": is_atlas,
            "masked_uri": mask_mongo_uri(uri),
            "message": mongo_stat["message"],
            "database": mongo_stat["database"]
        }
    })


@app.route("/api/kpis")
def kpis():
    df = get_cached_df()
    filtered = apply_filters(
        df,
        country=request.args.get("country"),
        category=request.args.get("category"),
        status=request.args.get("status")
    )
    return jsonify(get_overall_kpis(filtered))


@app.route("/api/monthly-trends")
def monthly_trends():
    df = get_cached_df()
    filtered = apply_filters(
        df,
        country=request.args.get("country"),
        category=request.args.get("category")
    )
    trends = get_monthly_trends(filtered)
    return jsonify(trends.to_dict(orient="records"))


@app.route("/api/top-products")
def top_products():
    n = int(request.args.get("n", 8))
    by = request.args.get("by", "revenue")
    df = get_cached_df()
    top_df = get_top_products(df, n=n, by=by)
    return jsonify(top_df.to_dict(orient="records"))


@app.route("/api/category-share")
def category_share():
    df = get_cached_df()
    cat_rev = (
        df[~df["IsCancelled"]]
        .groupby("Category")
        .agg(revenue=("Sales", "sum"), units=("Quantity", "sum"))
        .reset_index()
    )
    cat_rev["revenue"] = cat_rev["revenue"].round(2)
    return jsonify(cat_rev.to_dict(orient="records"))


@app.route("/api/cancellations")
def cancellations():
    df = get_cached_df()
    canc_data = get_cancellation_analysis(df)
    day_df = canc_data["day_pattern"].copy()
    day_list = []
    for _, row in day_df.iterrows():
        day_list.append({
            "day": str(row["DayOfWeek"]),
            "fulfilled": int(row.get(False, 0)),
            "cancelled": int(row.get(True, 0))
        })
    return jsonify({
        "top_returned_products": canc_data["top_returned_products"].to_dict(orient="records"),
        "country_cancellation_rates": canc_data["country_cancellation_rates"].head(10).to_dict(orient="records"),
        "day_pattern": day_list
    })


@app.route("/api/sdg12")
def sdg12():
    df = get_cached_df()
    metrics = get_sdg12_metrics(df)
    return jsonify({
        "wasted_packaging_kg": metrics["wasted_packaging_kg"],
        "fulfilled_packaging_kg": metrics["fulfilled_packaging_kg"],
        "returned_units": metrics["returned_units"],
        "durable_ratio_pct": metrics["durable_ratio_pct"],
        "durable_rev_share_pct": metrics["durable_rev_share_pct"],
        "category_metrics": metrics["category_metrics"].to_dict(orient="records"),
        "recommendations": metrics["recommendations"]
    })


@app.route("/api/sdg9")
def sdg9():
    df = get_cached_df()
    metrics = get_sdg9_metrics(df)
    return jsonify({
        "total_co2_kg": metrics["total_co2_kg"],
        "zone_summary": metrics["zone_summary"].to_dict(orient="records"),
        "country_logistics": metrics["country_logistics"].head(10).to_dict(orient="records"),
        "recommendations": metrics["recommendations"]
    })


@app.route("/api/filters")
def filters():
    df = get_cached_df()
    return jsonify({
        "countries": ["All"] + sorted(df["Country"].unique().tolist()),
        "categories": ["All"] + sorted(df["Category"].unique().tolist())
    })


@app.route("/api/data")
def data_records():
    df = get_cached_df()
    filtered = apply_filters(
        df,
        country=request.args.get("country"),
        category=request.args.get("category"),
        status=request.args.get("status")
    )
    q = request.args.get("q", "").strip()
    if q:
        mask = (
            filtered["Description"].str.contains(q, case=False, na=False) |
            filtered["InvoiceNo_str"].str.contains(q, case=False, na=False)
        )
        filtered = filtered[mask]
    limit = int(request.args.get("limit", 50))
    cols = ["InvoiceNo_str", "StockCode", "Description", "Quantity", "UnitPrice", "Sales", "Category", "Country", "IsCancelled"]
    return jsonify({
        "total_matches": len(filtered),
        "records": filtered[cols].head(limit).rename(columns={"InvoiceNo_str": "InvoiceNo"}).to_dict(orient="records")
    })


@app.route("/api/sql", methods=["POST"])
def run_sql():
    req = request.get_json() or {}
    key = req.get("query_key", "top5")
    t0 = time.time()
    
    if key == "top5":
        df = get_top_5_products_by_revenue()
        sql_text = "SELECT p.stock_code, p.description, p.category, SUM(oi.quantity)... ORDER BY total_revenue DESC LIMIT 5"
    elif key == "monthly":
        df = get_monthly_revenue_summary()
        sql_text = "SELECT substr(o.invoice_date, 1, 7) AS Month, COUNT(DISTINCT o.invoice_no)... GROUP BY Month"
    elif key == "join":
        df = get_joined_order_details(limit=15)
        sql_text = "SELECT o.invoice_no, o.country, p.stock_code... FROM orders JOIN order_items JOIN products"
    elif key == "subquery":
        df = get_products_exceeding_average_sales(limit=10)
        sql_text = "SELECT p.stock_code... HAVING SUM(total_price) > (SELECT AVG(sub_revenue)...)"
    elif key == "category":
        df = get_category_performance()
        sql_text = "SELECT p.category, COUNT(DISTINCT o.invoice_no)... GROUP BY p.category ORDER BY total_revenue DESC"
    elif key == "custom":
        custom_sql = req.get("custom_sql", "")
        df, err = execute_custom_sql(custom_sql)
        if err:
            return jsonify({"detail": f"SQL Error: {err}"}), 400
        sql_text = custom_sql
    else:
        return jsonify({"detail": "Unknown query_key"}), 400
        
    execution_ms = round((time.time() - t0) * 1000, 2)
    return jsonify({
        "sql": sql_text,
        "execution_time_ms": execution_ms,
        "row_count": len(df),
        "columns": list(df.columns),
        "data": df.to_dict(orient="records")
    })


@app.route("/api/mongo", methods=["POST"])
def run_mongo():
    req = request.get_json() or {}
    key = req.get("pipeline_key", "sdg_category")
    t0 = time.time()
    
    if key == "sdg_category":
        data = aggregate_sdg_by_category()
        desc = "db.sdg_indicators.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif key == "logistics_zone":
        data = aggregate_logistics_footprint()
        desc = "db.logistics_footprint.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif key == "recommendations":
        data = aggregate_recommendations_by_sdg()
        desc = "db.sdg_recommendations.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif key == "custom":
        col = req.get("custom_collection", "sdg_indicators")
        pipe_str = req.get("custom_pipeline_json", "[]")
        data, err = execute_custom_mongo_pipeline(col, pipe_str)
        if err:
            return jsonify({"detail": f"MongoDB Error: {err}"}), 400
        desc = f"db.{col}.aggregate({pipe_str})"
    else:
        return jsonify({"detail": "Unknown pipeline_key"}), 400
        
    execution_ms = round((time.time() - t0) * 1000, 2)
    return jsonify({
        "pipeline": desc,
        "execution_time_ms": execution_ms,
        "document_count": len(data),
        "documents": data
    })


@app.route("/api/sync-mongo", methods=["POST"])
def sync_mongo():
    t0 = time.time()
    reset_mongo_connection()
    df = get_cached_df()
    seed_result = sync_analytics_to_mongodb(df)
    status = get_mongo_status()
    execution_ms = round((time.time() - t0) * 1000, 2)
    return jsonify({
        "message": "MongoDB synced successfully!",
        "seeded": seed_result,
        "connection": status,
        "execution_time_ms": execution_ms
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Launching Flask Full-Stack Server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
