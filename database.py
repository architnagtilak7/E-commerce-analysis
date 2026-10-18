"""
database.py
===========
Unified Database Interface for DCDS Lab ESE Project.
Integrates both SQL and NoSQL engines required by the faculty rubric:
1. SQLite Relational 3NF Schema & Advanced SQL Queries (from sql_database.py)
2. MongoDB Atlas Cloud NoSQL & Aggregation Pipelines (from mongodb_database.py)
"""

# Re-export SQL functions and constants
from sql_database import (
    DEFAULT_DB_PATH,
    get_connection as get_sql_connection,
    init_database,
    populate_database_from_df,
    get_top_5_products_by_revenue,
    get_monthly_revenue_summary,
    get_joined_order_details,
    get_products_exceeding_average_sales,
    get_category_performance,
    execute_custom_sql
)

# Re-export MongoDB functions and constants
from mongodb_database import (
    DB_NAME as MONGO_DB_NAME,
    DEFAULT_MONGO_URI,
    get_mongo_client,
    get_database as get_mongo_database,
    get_connection_status as get_mongo_status,
    populate_sdg_documents,
    aggregate_sdg_by_category,
    aggregate_logistics_footprint,
    aggregate_recommendations_by_sdg,
    execute_custom_mongo_pipeline,
    reset_mongo_connection,
    mask_mongo_uri
)

# Unified Health Check Function
def check_all_databases():
    """Checks connectivity to both SQLite (SQL) and MongoDB Atlas (NoSQL)."""
    import os
    sqlite_ok = os.path.exists(DEFAULT_DB_PATH)
    mongo_stat = get_mongo_status()
    return {
        "sqlite": {
            "status": "connected" if sqlite_ok else "missing",
            "file": DEFAULT_DB_PATH
        },
        "mongodb": mongo_stat
    }


if __name__ == "__main__":
    print("Testing Unified Database Module (database.py)...")
    diag = check_all_databases()
    print("Diagnostics:", diag)
    print("Top 5 Products via SQL:")
    print(get_top_5_products_by_revenue().head(3))
    print("SDG Aggregation via MongoDB:")
    print(aggregate_sdg_by_category()[:2])
