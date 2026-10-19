"""
server.py
=========
FastAPI Web Application Server for SDG E-Commerce Analysis.
Features:
- Pure HTML5 / CSS3 / Vanilla JavaScript Frontend
- High-Performance SQLite Backend (Sub-10ms response times, ~40MB RAM usage)
- MongoDB NoSQL Integration (Atlas Cloud & Embedded fallback)
- Auto-seeding MongoDB collections on startup
- Safe Live SQL and MongoDB Aggregation Runners
"""

import os
import sys
import time
import json
import sqlite3
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

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
    populate_sdg_documents,
    reset_mongo_connection,
    mask_mongo_uri
)

app = FastAPI(
    title="SDG E-Commerce Sustainability API",
    description="Dual-Database (SQLite + MongoDB Atlas) Analytics Engine for DCDS Lab",
    version="2.1.0"
)

# Enable CORS for external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_sqlite_conn(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a connection to SQLite with row dictionary factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# Packaging weight estimates per unit (grams)
PACKAGING_WEIGHTS = {
    "Kitchenware & Dining": 85.0,
    "Home & Living": 110.0,
    "Stationery & Craft": 25.0,
    "Toys & Games": 60.0,
    "Bags & Accessories": 40.0,
    "Seasonal & Holiday": 45.0,
    "Other / Miscellaneous": 50.0,
}

# Standard ESG recommendations
SDG12_RECOMMENDATIONS = [
    {
        "id": "REC-12-01",
        "sdg_goal": "SDG 12",
        "title": "Return-Reason Logging at Checkout",
        "target": "Target 12.5 (Substantially Reduce Waste Generation)",
        "priority": "High",
        "description": "Institute mandatory digital return reason selection and item photo verification to distinguish transit damage from customer remorse.",
        "potential_reduction_pct": 28.4,
        "metric": "Return Volume Reduction",
        "timeline": "Immediate (Q1)"
    },
    {
        "id": "REC-12-02",
        "sdg_goal": "SDG 12",
        "title": "Switch High-Scrap Categories to Biodegradable Packaging",
        "target": "Target 12.2 (Sustainable Management of Natural Resources)",
        "priority": "High",
        "description": "Replace virgin bubble wrap with 100% recycled shredded corrugated cardboard and water-activated paper tape.",
        "potential_reduction_pct": 34.0,
        "metric": "Plastic Packaging Scrap",
        "timeline": "3 Months"
    },
    {
        "id": "REC-12-03",
        "sdg_goal": "SDG 12",
        "title": "Eco-Durability Badge for Catalog Items",
        "target": "Target 12.8 (Promote Sustainable Lifestyles)",
        "priority": "Medium",
        "description": "Add 'Long-Life Reusable' badge to high-durability items to guide consumer purchasing toward circular alternatives.",
        "potential_reduction_pct": 14.2,
        "metric": "Durable Goods Adoption",
        "timeline": "6 Months"
    }
]

SDG9_RECOMMENDATIONS = [
    {
        "id": "REC-09-01",
        "sdg_goal": "SDG 9",
        "title": "Electric Van Fleet for UK Domestic Corridor",
        "target": "Target 9.4 (Upgrade Infrastructure for Sustainability)",
        "priority": "High",
        "description": "Partner with green courier carriers operating 100% electric delivery vans for regional UK hubs.",
        "potential_reduction_pct": 42.0,
        "metric": "Domestic Delivery CO2e",
        "timeline": "4 Months"
    },
    {
        "id": "REC-09-02",
        "sdg_goal": "SDG 9",
        "title": "European Rail Consolidation Hub",
        "target": "Target 9.1 (Develop Sustainable Regional Transport)",
        "priority": "High",
        "description": "Shift freight from cross-border diesel road transport to electrified rail freight corridors across Germany, France, and Benelux.",
        "potential_reduction_pct": 31.8,
        "metric": "European Cross-Border CO2e",
        "timeline": "6 Months"
    },
    {
        "id": "REC-09-03",
        "sdg_goal": "SDG 9",
        "title": "Minimum Basket Threshold for Air Freight",
        "target": "Target 9.4 (Retrofit Freight Operations)",
        "priority": "Medium",
        "description": "Incentivize bulk purchasing for long-haul destinations (Australia, USA, Japan) through free shipping discounts for orders above 30 units.",
        "potential_reduction_pct": 19.5,
        "metric": "Per-Unit Transport Emissions",
        "timeline": "2 Months"
    }
]


def seed_mongodb_from_sqlite():
    """Extracts aggregates directly from SQLite and seeds MongoDB collections in milliseconds."""
    if not os.path.exists(DEFAULT_DB_PATH):
        return {"error": "SQLite database not found."}

    with get_sqlite_conn() as conn:
        # 1. Category SDG metrics
        cat_q = """
            SELECT 
                p.category,
                ROUND(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 2) as revenue,
                SUM(CASE WHEN o.is_cancelled = 0 THEN oi.quantity ELSE 0 END) as units_sold,
                SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.quantity) ELSE 0 END) as units_cancelled,
                ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN 1.0 ELSE 0.0 END) * 100.0 / NULLIF(COUNT(DISTINCT o.invoice_no), 0), 2) as return_rate_pct,
                ROUND(SUM(CASE WHEN p.is_durable = 1 AND o.is_cancelled = 0 THEN oi.quantity ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.quantity ELSE 0 END), 0), 2) as durable_share_pct
            FROM order_items oi
            JOIN products p ON oi.stock_code = p.stock_code
            JOIN orders o ON oi.invoice_no = o.invoice_no
            GROUP BY p.category;
        """
        cat_rows = conn.execute(cat_q).fetchall()
        category_docs = []
        for r in cat_rows:
            cat_name = str(r["category"])
            weight_g = PACKAGING_WEIGHTS.get(cat_name, 50.0)
            units_canc = int(r["units_cancelled"] or 0)
            pkg_kg = round(units_canc * weight_g / 1000.0, 2)
            category_docs.append({
                "category": cat_name,
                "status": "active",
                "revenue": float(r["revenue"] or 0.0),
                "units_sold": int(r["units_sold"] or 0),
                "cancelled_units": units_canc,
                "return_rate_pct": float(r["return_rate_pct"] or 0.0),
                "est_packaging_kg": pkg_kg,
                "durable_share_pct": float(r["durable_share_pct"] or 0.0)
            })

        # 2. Logistics footprint (SDG 9)
        log_q = """
            SELECT 
                o.country,
                o.logistics_zone as zone,
                COUNT(DISTINCT o.invoice_no) as order_count,
                SUM(o.total_items) as total_items,
                ROUND(SUM(o.total_amount), 2) as total_sales
            FROM orders o
            WHERE o.is_cancelled = 0
            GROUP BY o.country, o.logistics_zone;
        """
        log_rows = conn.execute(log_q).fetchall()
        co2_rates = {"UK Domestic": 0.45, "Europe Regional": 1.85, "International Air": 8.50}
        logistics_docs = []
        for r in log_rows:
            zone = str(r["zone"])
            ord_cnt = int(r["order_count"] or 0)
            tot_items = int(r["total_items"] or 0)
            co2_kg = round(ord_cnt * co2_rates.get(zone, 2.0), 2)
            avg_u = round(tot_items / ord_cnt, 1) if ord_cnt else 0.0
            logistics_docs.append({
                "country": str(r["country"]),
                "zone": zone,
                "order_count": ord_cnt,
                "total_co2_kg": co2_kg,
                "avg_units_per_order": avg_u,
                "total_sales": float(r["total_sales"] or 0.0)
            })

        # 3. Recommendations
        all_recs = []
        for r in SDG12_RECOMMENDATIONS + SDG9_RECOMMENDATIONS:
            all_recs.append({
                "rec_id": r["id"],
                "sdg_goal": r["sdg_goal"],
                "title": r["title"],
                "target": r["target"],
                "priority": r["priority"],
                "description": r["description"],
                "potential_reduction_pct": float(r["potential_reduction_pct"]),
                "metric": r["metric"],
                "timeline": r["timeline"]
            })

        return populate_sdg_documents(category_docs, logistics_docs, all_recs)


@app.on_event("startup")
def startup_event():
    """Initializes and auto-seeds MongoDB on application startup."""
    print("🚀 Initializing SDG E-Commerce Sustainability API...")
    try:
        seed_mongodb_from_sqlite()
        print("✓ MongoDB collections auto-seeded successfully from SQLite.")
    except Exception as e:
        print(f"Notice: Initial seeding warning: {e}")


# =========================================================================
# REST API ENDPOINTS
# =========================================================================

@app.head("/")
def head_root():
    """Handles Render health-check HEAD requests with 200 OK."""
    return Response(status_code=200)


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
            "mode": mongo_stat["mode"],
            "is_atlas": is_atlas,
            "masked_uri": mask_mongo_uri(uri),
            "message": mongo_stat["message"],
            "database": mongo_stat["database"]
        }
    }


@app.get("/api/filters")
def filter_options():
    """Returns distinct countries and categories for frontend dropdowns."""
    with get_sqlite_conn() as conn:
        countries = [r["country"] for r in conn.execute(
            "SELECT DISTINCT country FROM orders WHERE country IS NOT NULL ORDER BY country;"
        ).fetchall()]
        categories = [r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category;"
        ).fetchall()]

    return {
        "countries": ["All"] + countries,
        "categories": ["All"] + categories
    }


@app.get("/api/kpis")
def kpis(
    country: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None
):
    """Calculates headline commercial metrics directly from SQLite in milliseconds."""
    with get_sqlite_conn() as conn:
        needs_items = (category and category != "All")

        if not needs_items:
            where_clauses = []
            params = []
            if country and country != "All":
                where_clauses.append("country = ?")
                params.append(country)
            if status == "fulfilled":
                where_clauses.append("is_cancelled = 0")
            elif status == "cancelled":
                where_clauses.append("is_cancelled = 1")

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            q = f"""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN is_cancelled = 0 THEN 1 ELSE 0 END) as fulfilled_orders,
                    SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) as cancelled_orders,
                    ROUND(SUM(CASE WHEN is_cancelled = 0 THEN total_amount ELSE 0 END), 2) as gross_revenue,
                    ROUND(SUM(CASE WHEN is_cancelled = 1 THEN ABS(total_amount) ELSE 0 END), 2) as refund_amount,
                    ROUND(SUM(total_amount), 2) as net_revenue,
                    SUM(CASE WHEN is_cancelled = 0 THEN total_items ELSE 0 END) as total_units_sold,
                    COUNT(DISTINCT customer_id) as unique_customers
                FROM orders
                {where_sql};
            """
            row = dict(conn.execute(q, params).fetchone())
        else:
            where_clauses = []
            params = []
            if country and country != "All":
                where_clauses.append("o.country = ?")
                params.append(country)
            if category and category != "All":
                where_clauses.append("p.category = ?")
                params.append(category)
            if status == "fulfilled":
                where_clauses.append("o.is_cancelled = 0")
            elif status == "cancelled":
                where_clauses.append("o.is_cancelled = 1")

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            q = f"""
                SELECT 
                    COUNT(DISTINCT o.invoice_no) as total_orders,
                    COUNT(DISTINCT CASE WHEN o.is_cancelled = 0 THEN o.invoice_no END) as fulfilled_orders,
                    COUNT(DISTINCT CASE WHEN o.is_cancelled = 1 THEN o.invoice_no END) as cancelled_orders,
                    ROUND(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 2) as gross_revenue,
                    ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.total_price) ELSE 0 END), 2) as refund_amount,
                    ROUND(SUM(oi.total_price), 2) as net_revenue,
                    SUM(CASE WHEN o.is_cancelled = 0 THEN oi.quantity ELSE 0 END) as total_units_sold,
                    COUNT(DISTINCT o.customer_id) as unique_customers
                FROM orders o
                JOIN order_items oi ON o.invoice_no = oi.invoice_no
                JOIN products p ON oi.stock_code = p.stock_code
                {where_sql};
            """
            row = dict(conn.execute(q, params).fetchone())

    tot_orders = int(row["total_orders"] or 0)
    ful_orders = int(row["fulfilled_orders"] or 0)
    canc_orders = int(row["cancelled_orders"] or 0)
    gross_rev = float(row["gross_revenue"] or 0.0)
    refund_amt = float(row["refund_amount"] or 0.0)
    net_rev = float(row["net_revenue"] or 0.0)
    tot_units = int(row["total_units_sold"] or 0)
    uniq_cust = int(row["unique_customers"] or 0)

    canc_rate = round(canc_orders * 100.0 / tot_orders, 2) if tot_orders else 0.0
    aov = round(gross_rev / ful_orders, 2) if ful_orders else 0.0

    return {
        "gross_revenue": gross_rev,
        "refund_amount": refund_amt,
        "net_revenue": net_rev,
        "total_orders": tot_orders,
        "fulfilled_orders": ful_orders,
        "cancelled_orders": canc_orders,
        "cancellation_rate_pct": canc_rate,
        "total_units_sold": tot_units,
        "avg_order_value": aov,
        "unique_customers": uniq_cust
    }


@app.get("/api/monthly-trends")
def monthly_trends(
    country: Optional[str] = None,
    category: Optional[str] = None
):
    """Returns monthly financial and return volume trends."""
    with get_sqlite_conn() as conn:
        needs_items = (category and category != "All")

        if not needs_items:
            where_sql = "WHERE country = ?" if (country and country != "All") else ""
            params = [country] if where_sql else []
            q = f"""
                SELECT 
                    substr(invoice_date, 1, 7) AS YearMonth,
                    COUNT(invoice_no) AS total_orders,
                    SUM(CASE WHEN is_cancelled = 0 THEN 1 ELSE 0 END) AS fulfilled_orders,
                    SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) AS cancelled_orders,
                    ROUND(SUM(CASE WHEN is_cancelled = 0 THEN total_amount ELSE 0 END), 2) AS fulfilled_revenue,
                    ROUND(SUM(CASE WHEN is_cancelled = 1 THEN ABS(total_amount) ELSE 0 END), 2) AS refund_amount,
                    ROUND(SUM(total_amount), 2) AS net_revenue
                FROM orders
                {where_sql}
                GROUP BY substr(invoice_date, 1, 7)
                ORDER BY YearMonth ASC;
            """
            rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        else:
            where_clauses = []
            params = []
            if country and country != "All":
                where_clauses.append("o.country = ?")
                params.append(country)
            if category and category != "All":
                where_clauses.append("p.category = ?")
                params.append(category)
            where_sql = "WHERE " + " AND ".join(where_clauses)
            q = f"""
                SELECT 
                    substr(o.invoice_date, 1, 7) AS YearMonth,
                    COUNT(DISTINCT o.invoice_no) AS total_orders,
                    COUNT(DISTINCT CASE WHEN o.is_cancelled = 0 THEN o.invoice_no END) AS fulfilled_orders,
                    COUNT(DISTINCT CASE WHEN o.is_cancelled = 1 THEN o.invoice_no END) AS cancelled_orders,
                    ROUND(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 2) AS fulfilled_revenue,
                    ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.total_price) ELSE 0 END), 2) AS refund_amount,
                    ROUND(SUM(oi.total_price), 2) AS net_revenue
                FROM orders o
                JOIN order_items oi ON o.invoice_no = oi.invoice_no
                JOIN products p ON oi.stock_code = p.stock_code
                {where_sql}
                GROUP BY substr(o.invoice_date, 1, 7)
                ORDER BY YearMonth ASC;
            """
            rows = [dict(r) for r in conn.execute(q, params).fetchall()]

    return rows


@app.get("/api/top-products")
def top_products(
    n: int = Query(8, ge=1, le=50),
    by: str = Query("revenue", pattern="^(revenue|units)$")
):
    """Returns top N products sorted by revenue or quantity sold."""
    limit_n = int(getattr(n, "default", n) if hasattr(n, "default") else n)
    order_col = "revenue" if by == "revenue" else "units"
    with get_sqlite_conn() as conn:
        q = f"""
            SELECT 
                p.stock_code AS StockCode,
                p.description AS Description,
                p.category AS Category,
                SUM(oi.quantity) AS units,
                ROUND(SUM(oi.total_price), 2) AS revenue
            FROM order_items oi
            JOIN products p ON oi.stock_code = p.stock_code
            JOIN orders o ON oi.invoice_no = o.invoice_no
            WHERE o.is_cancelled = 0 AND oi.quantity > 0
            GROUP BY p.stock_code, p.description, p.category
            ORDER BY {order_col} DESC
            LIMIT ?;
        """
        rows = [dict(r) for r in conn.execute(q, (limit_n,)).fetchall()]
    return rows


@app.get("/api/category-share")
def category_share():
    """Returns product category distribution."""
    with get_sqlite_conn() as conn:
        q = """
            SELECT 
                p.category AS Category,
                ROUND(SUM(oi.total_price), 2) AS revenue,
                SUM(oi.quantity) AS units
            FROM order_items oi
            JOIN products p ON oi.stock_code = p.stock_code
            JOIN orders o ON oi.invoice_no = o.invoice_no
            WHERE o.is_cancelled = 0 AND oi.quantity > 0
            GROUP BY p.category
            ORDER BY revenue DESC;
        """
        rows = [dict(r) for r in conn.execute(q).fetchall()]
    return rows


@app.get("/api/cancellations")
def cancellation_deep_dive():
    """Returns return and cancellation patterns."""
    with get_sqlite_conn() as conn:
        # 1. Top returned products
        top_ret_q = """
            SELECT 
                p.stock_code as StockCode,
                p.description as Description,
                p.category as Category,
                ABS(SUM(oi.quantity)) as return_quantity,
                ROUND(ABS(SUM(oi.total_price)), 2) as refund_amount
            FROM order_items oi
            JOIN products p ON oi.stock_code = p.stock_code
            JOIN orders o ON oi.invoice_no = o.invoice_no
            WHERE o.is_cancelled = 1
            GROUP BY p.stock_code, p.description, p.category
            ORDER BY return_quantity DESC
            LIMIT 10;
        """
        top_returned = [dict(r) for r in conn.execute(top_ret_q).fetchall()]

        # 2. Country cancellation rates
        country_q = """
            SELECT 
                o.country as Country,
                COUNT(DISTINCT o.invoice_no) as "Total Orders",
                SUM(CASE WHEN o.is_cancelled = 1 THEN 1 ELSE 0 END) as "Cancelled Orders",
                ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(DISTINCT o.invoice_no), 2) as "Cancellation Rate (%)"
            FROM orders o
            GROUP BY o.country
            HAVING COUNT(DISTINCT o.invoice_no) >= 15
            ORDER BY "Cancellation Rate (%)" DESC
            LIMIT 10;
        """
        country_rates = [dict(r) for r in conn.execute(country_q).fetchall()]

        # 3. Day of week pattern
        day_q = """
            SELECT 
                CASE cast(strftime('%w', invoice_date) as integer)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    ELSE 'Saturday'
                END as day,
                SUM(CASE WHEN is_cancelled = 0 THEN 1 ELSE 0 END) as fulfilled,
                SUM(CASE WHEN is_cancelled = 1 THEN 1 ELSE 0 END) as cancelled
            FROM orders
            GROUP BY cast(strftime('%w', invoice_date) as integer)
            ORDER BY cast(strftime('%w', invoice_date) as integer);
        """
        days = [dict(r) for r in conn.execute(day_q).fetchall()]

    return {
        "top_returned_products": top_returned,
        "country_cancellation_rates": country_rates,
        "day_pattern": days
    }


@app.get("/api/sdg12")
def sdg12_metrics():
    """Returns SDG 12 Responsible Consumption & Waste metrics."""
    # Attempt to pull from MongoDB aggregation first
    mongo_cats = aggregate_sdg_by_category()
    if mongo_cats:
        with get_sqlite_conn() as conn:
            summary = conn.execute("""
                SELECT 
                    SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.quantity) ELSE 0 END) as returned_units,
                    ROUND(SUM(CASE WHEN p.is_durable = 1 AND o.is_cancelled = 0 THEN oi.quantity ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.quantity ELSE 0 END), 0), 2) as durable_ratio_pct,
                    ROUND(SUM(CASE WHEN p.is_durable = 1 AND o.is_cancelled = 0 THEN oi.total_price ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 0), 2) as durable_rev_share_pct
                FROM order_items oi
                JOIN products p ON oi.stock_code = p.stock_code
                JOIN orders o ON oi.invoice_no = o.invoice_no;
            """).fetchone()

        wasted_pkg = sum(c.get("Est Packaging Footprint (kg)", 0) for c in mongo_cats)
        return {
            "wasted_packaging_kg": round(wasted_pkg, 2),
            "fulfilled_packaging_kg": round(wasted_pkg * 6.5, 2),
            "returned_units": int(summary["returned_units"] or 0),
            "durable_ratio_pct": float(summary["durable_ratio_pct"] or 0.0),
            "durable_rev_share_pct": float(summary["durable_rev_share_pct"] or 0.0),
            "category_metrics": mongo_cats,
            "recommendations": SDG12_RECOMMENDATIONS
        }

    # Fallback to direct calculation
    seed_mongodb_from_sqlite()
    return sdg12_metrics()


@app.get("/api/sdg9")
def sdg9_metrics():
    """Returns SDG 9 Sustainable Infrastructure & Freight Emissions metrics."""
    mongo_logistics = aggregate_logistics_footprint()
    if not mongo_logistics:
        seed_mongodb_from_sqlite()
        mongo_logistics = aggregate_logistics_footprint()

    total_co2 = sum(z.get("Total Freight CO2 (kg)", 0) for z in mongo_logistics)

    with get_sqlite_conn() as conn:
        country_q = """
            SELECT 
                country as Country,
                logistics_zone as LogisticsZone,
                COUNT(DISTINCT invoice_no) as order_count,
                ROUND(SUM(total_amount), 2) as total_sales
            FROM orders
            WHERE is_cancelled = 0
            GROUP BY country, logistics_zone
            ORDER BY order_count DESC
            LIMIT 10;
        """
        country_rows = [dict(r) for r in conn.execute(country_q).fetchall()]

    return {
        "total_co2_kg": round(total_co2, 2),
        "zone_summary": mongo_logistics,
        "country_logistics": country_rows,
        "recommendations": SDG9_RECOMMENDATIONS
    }


@app.get("/api/data")
def data_explorer(
    q: Optional[str] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """Returns filtered transaction records directly from SQLite with pagination."""
    where_clauses = []
    params = []

    if country and country != "All":
        where_clauses.append("o.country = ?")
        params.append(country)
    if category and category != "All":
        where_clauses.append("p.category = ?")
        params.append(category)
    if status == "fulfilled":
        where_clauses.append("o.is_cancelled = 0")
    elif status == "cancelled":
        where_clauses.append("o.is_cancelled = 1")
    if q and q.strip():
        term = f"%{q.strip()}%"
        where_clauses.append("(p.description LIKE ? OR o.invoice_no LIKE ? OR p.stock_code LIKE ?)")
        params.extend([term, term, term])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with get_sqlite_conn() as conn:
        count_q = f"""
            SELECT COUNT(*)
            FROM orders o
            JOIN order_items oi ON o.invoice_no = oi.invoice_no
            JOIN products p ON oi.stock_code = p.stock_code
            {where_sql};
        """
        total_matches = conn.execute(count_q, params).fetchone()[0]

        data_q = f"""
            SELECT 
                o.invoice_no AS InvoiceNo,
                p.stock_code AS StockCode,
                p.description AS Description,
                oi.quantity AS Quantity,
                oi.unit_price AS UnitPrice,
                oi.total_price AS Sales,
                p.category AS Category,
                o.country AS Country,
                o.is_cancelled AS IsCancelled
            FROM orders o
            JOIN order_items oi ON o.invoice_no = oi.invoice_no
            JOIN products p ON oi.stock_code = p.stock_code
            {where_sql}
            ORDER BY o.invoice_date DESC
            LIMIT ?;
        """
        limit_val = int(getattr(limit, "default", limit) if hasattr(limit, "default") else limit)
        records = [dict(r) for r in conn.execute(data_q, params + [limit_val]).fetchall()]

    return {
        "total_matches": total_matches,
        "records": records
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
        sql_text = "SELECT substr(o.invoice_date, 1, 7) AS Month, COUNT(o.invoice_no)... GROUP BY Month"
    elif req.query_key == "join":
        df = get_joined_order_details(limit=15)
        sql_text = "SELECT o.invoice_no, o.country, p.description, oi.quantity... JOIN products JOIN orders LIMIT 15"
    elif req.query_key == "subquery":
        df = get_products_exceeding_average_sales(limit=10)
        sql_text = "SELECT p.stock_code... HAVING SUM(total_price) > (SELECT AVG(sub_revenue)...)"
    elif req.query_key == "category":
        df = get_category_performance()
        sql_text = "SELECT p.category, COUNT(orders), SUM(quantity), Durable Share (%)... GROUP BY category"
    elif req.query_key == "custom":
        if not req.custom_sql or not req.custom_sql.strip():
            raise HTTPException(status_code=400, detail="Custom SQL query cannot be empty.")
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
def execute_mongo_pipeline(req: MongoRequest):
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
    """On-demand endpoint to seed current MongoDB target (Atlas or embedded) in milliseconds."""
    t0 = time.time()
    reset_mongo_connection()
    seed_result = seed_mongodb_from_sqlite()
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

base_dir = os.path.dirname(__file__)
static_dir = os.path.join(base_dir, "static") if os.path.exists(os.path.join(base_dir, "static")) else os.path.join(base_dir, "frontend")
templates_dir = os.path.join(base_dir, "templates") if os.path.exists(os.path.join(base_dir, "templates")) else os.path.join(base_dir, "frontend")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_index():
    """Serves the main HTML5 / CSS3 / Vanilla JS single-page application."""
    index_path = os.path.join(templates_dir, "index.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend index.html not found."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Launching SDG E-Commerce Full-Stack Server on port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
