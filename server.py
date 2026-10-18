"""
server.py
=========
FastAPI Web Application Server for SDG E-Commerce Analysis.
Serves:
- Pure HTML5 / CSS3 / Vanilla JavaScript Frontend
- REST API Endpoints for KPIs, Monthly Trends, SDG 12 & 9 Analytics
- Live SQL Relational Runner (SQLite)
- Live MongoDB NoSQL Aggregation Runner (Atlas / Local / Embedded)
- On-Demand Atlas Cloud Database Sync
"""

import os
import time
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from data_cleaning import get_or_create_cleaned_data
from sql_database import (
    DEFAULT_DB_PATH,
    get_top_5_products_by_revenue,
    get_monthly_revenue_summary,
    get_joined_order_details,
    get_products_exceeding_average_sales,
    get_category_performance,
    execute_custom_sql
)
from mongodb_database import (
    get_connection_status,
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

app = FastAPI(
    title="SDG E-Commerce Sustainability API",
    description="Dual-Database (SQLite + MongoDB Atlas) Analytics Engine for DCDS Lab",
    version="2.0.0"
)

# Enable CORS for external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache in-memory cleaned dataframe for sub-millisecond API responses
_DF_CACHE = None


def get_cached_df():
    global _DF_CACHE
    if _DF_CACHE is None:
        _DF_CACHE = get_or_create_cleaned_data()
    return _DF_CACHE


def apply_filters(
    df,
    country: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    filtered = df.copy()
    if country and country != "All":
        filtered = filtered[filtered["Country"] == country]
    if category and category != "All":
        filtered = filtered[filtered["Category"] == category]
    if status == "fulfilled":
        filtered = filtered[~filtered["IsCancelled"]]
    elif status == "cancelled":
        filtered = filtered[filtered["IsCancelled"]]
    if start_date:
        filtered = filtered[filtered["InvoiceDate"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered["InvoiceDate"] <= pd.to_datetime(end_date)]
    return filtered


# =========================================================================
# REST API ENDPOINTS
# =========================================================================

@app.get("/api/health")
def health_status():
    """Returns database connection diagnostics for UI status pills."""
    mongo_stat = get_connection_status()
    sqlite_ready = os.path.exists(DEFAULT_DB_PATH)
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    is_atlas = "mongodb+srv://" in uri or "mongodb.net" in uri
    
    return {
        "status": "online",
        "sqlite": {
            "connected": sqlite_ready,
            "database": "data/ecommerce.db"
        },
        "mongodb": {
            "connected": mongo_stat["connected"],
            "mode": mongo_stat["mode"],  # "live" or "embedded"
            "is_atlas": is_atlas,
            "masked_uri": mask_mongo_uri(uri),
            "message": mongo_stat["message"],
            "database": mongo_stat["database"]
        }
    }


@app.get("/api/kpis")
def kpis(
    country: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """Calculates headline commercial metrics."""
    df = get_cached_df()
    filtered = apply_filters(df, country=country, category=category, status=status)
    return get_overall_kpis(filtered)


@app.get("/api/monthly-trends")
def monthly_trends(
    country: Optional[str] = None,
    category: Optional[str] = None
):
    """Returns monthly financial and return volume trends."""
    df = get_cached_df()
    filtered = apply_filters(df, country=country, category=category)
    trends = get_monthly_trends(filtered)
    return trends.to_dict(orient="records")


@app.get("/api/top-products")
def top_products(
    n: int = Query(8, ge=1, le=50),
    by: str = Query("revenue", pattern="^(revenue|units)$")
):
    """Returns top N products sorted by revenue or quantity sold."""
    df = get_cached_df()
    top_df = get_top_products(df, n=n, by=by)
    return top_df.to_dict(orient="records")


@app.get("/api/category-share")
def category_share():
    """Returns product category distribution."""
    df = get_cached_df()
    cat_rev = (
        df[~df["IsCancelled"]]
        .groupby("Category")
        .agg(revenue=("Sales", "sum"), units=("Quantity", "sum"))
        .reset_index()
    )
    cat_rev["revenue"] = cat_rev["revenue"].round(2)
    return cat_rev.to_dict(orient="records")


@app.get("/api/cancellations")
def cancellation_deep_dive():
    """Returns return and cancellation patterns."""
    df = get_cached_df()
    canc_data = get_cancellation_analysis(df)
    
    # Format day pattern for clean JSON serialization
    day_df = canc_data["day_pattern"].copy()
    day_list = []
    for _, row in day_df.iterrows():
        day_list.append({
            "day": str(row["DayOfWeek"]),
            "fulfilled": int(row.get(False, 0)),
            "cancelled": int(row.get(True, 0))
        })
        
    return {
        "top_returned_products": canc_data["top_returned_products"].to_dict(orient="records"),
        "country_cancellation_rates": canc_data["country_cancellation_rates"].head(10).to_dict(orient="records"),
        "day_pattern": day_list
    }


@app.get("/api/sdg12")
def sdg12_metrics():
    """Returns SDG 12 Responsible Consumption & Waste metrics."""
    df = get_cached_df()
    sdg12 = get_sdg12_metrics(df)
    return {
        "wasted_packaging_kg": sdg12["wasted_packaging_kg"],
        "fulfilled_packaging_kg": sdg12["fulfilled_packaging_kg"],
        "returned_units": sdg12["returned_units"],
        "durable_ratio_pct": sdg12["durable_ratio_pct"],
        "durable_rev_share_pct": sdg12["durable_rev_share_pct"],
        "category_metrics": sdg12["category_metrics"].to_dict(orient="records"),
        "recommendations": sdg12["recommendations"]
    }


@app.get("/api/sdg9")
def sdg9_metrics():
    """Returns SDG 9 Sustainable Infrastructure & Freight Emissions metrics."""
    df = get_cached_df()
    sdg9 = get_sdg9_metrics(df)
    return {
        "total_co2_kg": sdg9["total_co2_kg"],
        "zone_summary": sdg9["zone_summary"].to_dict(orient="records"),
        "country_logistics": sdg9["country_logistics"].head(10).to_dict(orient="records"),
        "recommendations": sdg9["recommendations"]
    }


@app.get("/api/filters")
def filter_options():
    """Returns distinct countries and categories for frontend dropdowns."""
    df = get_cached_df()
    countries = sorted(df["Country"].unique().tolist())
    categories = sorted(df["Category"].unique().tolist())
    return {
        "countries": ["All"] + countries,
        "categories": ["All"] + categories
    }


@app.get("/api/data")
def data_explorer(
    q: Optional[str] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """Returns filtered transaction records for data table explorer."""
    df = get_cached_df()
    filtered = apply_filters(df, country=country, category=category, status=status)
    if q and q.strip():
        term = q.strip()
        mask = (
            filtered["Description"].str.contains(term, case=False, na=False) |
            filtered["InvoiceNo_str"].str.contains(term, case=False, na=False)
        )
        filtered = filtered[mask]
        
    cols = [
        "InvoiceNo_str", "StockCode", "Description", "Quantity",
        "UnitPrice", "Sales", "Category", "Country", "IsCancelled"
    ]
    return {
        "total_matches": len(filtered),
        "records": filtered[cols].head(limit).rename(columns={"InvoiceNo_str": "InvoiceNo"}).to_dict(orient="records")
    }


# =========================================================================
# LIVE DATABASE QUERY PLAYGROUND ENDPOINTS
# =========================================================================

class SQLRequest(BaseModel):
    query_key: str
    custom_sql: Optional[str] = None


@app.post("/api/sql")
def execute_sql_query(req: SQLRequest):
    """Executes preset or custom SQL queries on SQLite."""
    t0 = time.time()
    
    if req.query_key == "top5":
        df = get_top_5_products_by_revenue()
        sql_text = "SELECT p.stock_code, p.description, p.category, SUM(oi.quantity)... ORDER BY total_revenue DESC LIMIT 5"
    elif req.query_key == "monthly":
        df = get_monthly_revenue_summary()
        sql_text = "SELECT substr(o.invoice_date, 1, 7) AS Month, COUNT(DISTINCT o.invoice_no)... GROUP BY Month"
    elif req.query_key == "join":
        df = get_joined_order_details(limit=15)
        sql_text = "SELECT o.invoice_no, o.country, p.stock_code, p.description... FROM orders JOIN order_items JOIN products"
    elif req.query_key == "subquery":
        df = get_products_exceeding_average_sales(limit=10)
        sql_text = "SELECT p.stock_code, p.description... HAVING SUM(total_price) > (SELECT AVG(sub_revenue)...)"
    elif req.query_key == "category":
        df = get_category_performance()
        sql_text = "SELECT p.category, COUNT(DISTINCT o.invoice_no)... GROUP BY p.category ORDER BY total_revenue DESC"
    elif req.query_key == "custom":
        if not req.custom_sql:
            raise HTTPException(status_code=400, detail="Missing custom_sql field.")
        df, err = execute_custom_sql(req.custom_sql)
        if err:
            raise HTTPException(status_code=400, detail=f"SQL Execution Error: {err}")
        sql_text = req.custom_sql
    else:
        raise HTTPException(status_code=400, detail="Unknown query_key.")
        
    execution_ms = round((time.time() - t0) * 1000, 2)
    return {
        "sql": sql_text,
        "execution_time_ms": execution_ms,
        "row_count": len(df),
        "columns": list(df.columns),
        "data": df.to_dict(orient="records")
    }


class MongoRequest(BaseModel):
    pipeline_key: str
    custom_collection: Optional[str] = None
    custom_pipeline_json: Optional[str] = None


@app.post("/api/mongo")
def execute_mongo_query(req: MongoRequest):
    """Executes preset or custom MongoDB aggregation pipelines."""
    t0 = time.time()
    
    if req.pipeline_key == "sdg_category":
        data = aggregate_sdg_by_category()
        pipeline_desc = "db.sdg_indicators.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif req.pipeline_key == "logistics_zone":
        data = aggregate_logistics_footprint()
        pipeline_desc = "db.logistics_footprint.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif req.pipeline_key == "recommendations":
        data = aggregate_recommendations_by_sdg()
        pipeline_desc = "db.sdg_recommendations.aggregate([{ $match }, { $group }, { $sort }, { $project }])"
    elif req.pipeline_key == "custom":
        if not req.custom_collection or not req.custom_pipeline_json:
            raise HTTPException(status_code=400, detail="Missing custom_collection or custom_pipeline_json.")
        data, err = execute_custom_mongo_pipeline(req.custom_collection, req.custom_pipeline_json)
        if err:
            raise HTTPException(status_code=400, detail=f"MongoDB Pipeline Error: {err}")
        pipeline_desc = f"db.{req.custom_collection}.aggregate({req.custom_pipeline_json})"
    else:
        raise HTTPException(status_code=400, detail="Unknown pipeline_key.")
        
    execution_ms = round((time.time() - t0) * 1000, 2)
    return {
        "pipeline": pipeline_desc,
        "execution_time_ms": execution_ms,
        "document_count": len(data),
        "documents": data
    }


@app.post("/api/sync-mongo")
def sync_mongo_atlas():
    """On-demand endpoint to seed current MongoDB target (Atlas or local)."""
    t0 = time.time()
    reset_mongo_connection()
    df = get_cached_df()
    seed_result = sync_analytics_to_mongodb(df)
    status = get_connection_status()
    execution_ms = round((time.time() - t0) * 1000, 2)
    return {
        "message": "MongoDB synced successfully!",
        "seeded": seed_result,
        "connection": status,
        "execution_time_ms": execution_ms
    }


# =========================================================================
# FRONTEND STATIC ASSETS & SPA ROUTING
# =========================================================================

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def serve_index():
    """Serves the main HTML5 / CSS3 / Vanilla JS single-page application."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend index.html is being prepared."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Launching SDG E-Commerce Full-Stack Server on port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
