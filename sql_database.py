"""
sql_database.py
===============
SQLite Relational Database Integration for SDG E-commerce Analysis.
Implements:
- 3NF Relational Schema: products, customers, orders, order_items
- Ingestion pipeline from cleaned DataFrame
- Advanced SQL Queries:
  1. Top 5 products by revenue
  2. Monthly revenue using GROUP BY
  3. SQL JOIN between product and order tables
  4. Subquery identifying products exceeding average sales
  5. Category-wise performance and sustainability metrics
- Safe query execution interface for Streamlit Live Query Runner
"""

import os
import sqlite3
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional

DEFAULT_DB_PATH = "data/ecommerce.db"


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates a connection to the SQLite database."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes tables and indexes in SQLite."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                stock_code TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL,
                is_durable INTEGER NOT NULL DEFAULT 0
            );
        """)
        
        # 2. Customers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                country TEXT NOT NULL,
                is_guest INTEGER NOT NULL DEFAULT 0
            );
        """)
        
        # 3. Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                invoice_no TEXT PRIMARY KEY,
                customer_id INTEGER,
                invoice_date TEXT NOT NULL,
                country TEXT NOT NULL,
                is_cancelled INTEGER NOT NULL DEFAULT 0,
                total_items INTEGER NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                logistics_zone TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            );
        """)
        
        # 4. Order Items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                FOREIGN KEY (invoice_no) REFERENCES orders(invoice_no),
                FOREIGN KEY (stock_code) REFERENCES products(stock_code)
            );
        """)
        
        # Indexes for query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(invoice_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_cancelled ON orders(is_cancelled);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_inv ON order_items(invoice_no);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_stock ON order_items(stock_code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category);")
        
        conn.commit()


def populate_database_from_df(df: pd.DataFrame, db_path: str = DEFAULT_DB_PATH) -> Dict[str, int]:
    """
    Populates SQLite tables from a cleaned DataFrame.
    Returns counts of inserted records.
    """
    init_database(db_path)
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Clear existing data for fresh ingestion
        cursor.execute("DELETE FROM order_items;")
        cursor.execute("DELETE FROM orders;")
        cursor.execute("DELETE FROM customers;")
        cursor.execute("DELETE FROM products;")
        conn.commit()
        
        # 1. Deduplicate and insert products
        # Choose the most frequent description and maximum unit price for each stock_code
        products_df = df.groupby("StockCode").agg({
            "Description": "first",
            "Category": "first",
            "UnitPrice": "max",
            "IsDurable": "first"
        }).reset_index()
        
        products_records = [
            (str(row["StockCode"]), str(row["Description"]), str(row["Category"]), float(row["UnitPrice"]), int(row["IsDurable"]))
            for _, row in products_df.iterrows()
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO products (stock_code, description, category, unit_price, is_durable)
            VALUES (?, ?, ?, ?, ?)
        """, products_records)
        
        # 2. Customers
        customers_df = df.groupby("CustomerID").agg({
            "Country": "first",
            "IsGuest": "first"
        }).reset_index()
        customers_records = [
            (int(row["CustomerID"]), str(row["Country"]), int(row["IsGuest"]))
            for _, row in customers_df.iterrows()
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO customers (customer_id, country, is_guest)
            VALUES (?, ?, ?)
        """, customers_records)
        
        # 3. Orders
        orders_df = df.groupby("InvoiceNo_str").agg({
            "CustomerID": "first",
            "InvoiceDate": "first",
            "Country": "first",
            "IsCancelled": "first",
            "Quantity": "sum",
            "Sales": "sum",
            "LogisticsZone": "first"
        }).reset_index()
        orders_records = [
            (
                str(row["InvoiceNo_str"]),
                int(row["CustomerID"]),
                str(row["InvoiceDate"]),
                str(row["Country"]),
                int(row["IsCancelled"]),
                int(row["Quantity"]),
                round(float(row["Sales"]), 2),
                str(row["LogisticsZone"])
            )
            for _, row in orders_df.iterrows()
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO orders (invoice_no, customer_id, invoice_date, country, is_cancelled, total_items, total_amount, logistics_zone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, orders_records)
        
        # 4. Order Items
        order_items_records = [
            (
                str(row["InvoiceNo_str"]),
                str(row["StockCode"]),
                int(row["Quantity"]),
                float(row["UnitPrice"]),
                round(float(row["Sales"]), 2)
            )
            for _, row in df.iterrows()
        ]
        cursor.executemany("""
            INSERT INTO order_items (invoice_no, stock_code, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?)
        """, order_items_records)
        
        conn.commit()
        
    counts = {
        "products": len(products_records),
        "customers": len(customers_records),
        "orders": len(orders_records),
        "order_items": len(order_items_records)
    }
    return counts


# =========================================================================
# ADVANCED SQL QUERIES (Faculty Requirement for DCDS Lab ESE)
# =========================================================================

def get_top_5_products_by_revenue(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Advanced Query 1: Top 5 products by revenue.
    Aggregates order items for fulfilled orders to find top earning items.
    """
    query = """
        SELECT 
            p.stock_code AS "Stock Code",
            p.description AS "Product Description",
            p.category AS "Category",
            SUM(oi.quantity) AS "Units Sold",
            ROUND(SUM(oi.total_price), 2) AS "Total Revenue ($)",
            CASE WHEN p.is_durable = 1 THEN 'Durable' ELSE 'Single-Use' END AS "Eco Durability"
        FROM order_items oi
        JOIN products p ON oi.stock_code = p.stock_code
        JOIN orders o ON oi.invoice_no = o.invoice_no
        WHERE o.is_cancelled = 0 AND oi.quantity > 0
        GROUP BY p.stock_code, p.description, p.category, p.is_durable
        ORDER BY "Total Revenue ($)" DESC
        LIMIT 5;
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn)


def get_monthly_revenue_summary(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Advanced Query 2: Monthly revenue using GROUP BY.
    Calculates fulfilled gross sales, cancellation refunds, and net revenue per month.
    """
    query = """
        SELECT 
            substr(o.invoice_date, 1, 7) AS "Month",
            COUNT(DISTINCT o.invoice_no) AS "Total Invoices",
            SUM(CASE WHEN o.is_cancelled = 0 THEN 1 ELSE 0 END) AS "Fulfilled Orders",
            SUM(CASE WHEN o.is_cancelled = 1 THEN 1 ELSE 0 END) AS "Cancelled Orders",
            ROUND(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 2) AS "Gross Revenue ($)",
            ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.total_price) ELSE 0 END), 2) AS "Refunds ($)",
            ROUND(SUM(oi.total_price), 2) AS "Net Revenue ($)"
        FROM orders o
        JOIN order_items oi ON o.invoice_no = oi.invoice_no
        GROUP BY substr(o.invoice_date, 1, 7)
        ORDER BY "Month" ASC;
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn)


def get_joined_order_details(db_path: str = DEFAULT_DB_PATH, limit: int = 15) -> pd.DataFrame:
    """
    Advanced Query 3: Multi-table SQL JOIN between orders, order_items, and products.
    """
    query = f"""
        SELECT 
            o.invoice_no AS "Invoice No",
            substr(o.invoice_date, 1, 10) AS "Date",
            o.country AS "Country",
            o.logistics_zone AS "Freight Zone",
            p.stock_code AS "Stock Code",
            p.description AS "Description",
            p.category AS "Category",
            oi.quantity AS "Quantity",
            oi.unit_price AS "Unit Price",
            oi.total_price AS "Total Price ($)"
        FROM orders o
        JOIN order_items oi ON o.invoice_no = oi.invoice_no
        JOIN products p ON oi.stock_code = p.stock_code
        WHERE o.is_cancelled = 0
        ORDER BY o.invoice_date DESC
        LIMIT {limit};
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn)


def get_products_exceeding_average_sales(db_path: str = DEFAULT_DB_PATH, limit: int = 10) -> pd.DataFrame:
    """
    Advanced Query 4: Subquery to identify products whose sales exceed the average sales.
    Calculates overall average revenue per product via subquery, then filters above-average items.
    """
    query = f"""
        SELECT 
            p.stock_code AS "Stock Code",
            p.description AS "Description",
            p.category AS "Category",
            SUM(oi.quantity) AS "Total Quantity",
            ROUND(SUM(oi.total_price), 2) AS "Product Revenue ($)",
            ROUND((
                SELECT AVG(sub_revenue)
                FROM (
                    SELECT SUM(sub_oi.total_price) AS sub_revenue
                    FROM order_items sub_oi
                    JOIN orders sub_o ON sub_oi.invoice_no = sub_o.invoice_no
                    WHERE sub_o.is_cancelled = 0 AND sub_oi.quantity > 0
                    GROUP BY sub_oi.stock_code
                )
            ), 2) AS "Catalog Avg Revenue ($)"
        FROM order_items oi
        JOIN products p ON oi.stock_code = p.stock_code
        JOIN orders o ON oi.invoice_no = o.invoice_no
        WHERE o.is_cancelled = 0 AND oi.quantity > 0
        GROUP BY p.stock_code, p.description, p.category
        HAVING SUM(oi.total_price) > (
            SELECT AVG(sub_revenue)
            FROM (
                SELECT SUM(sub_oi.total_price) AS sub_revenue
                FROM order_items sub_oi
                JOIN orders sub_o ON sub_oi.invoice_no = sub_o.invoice_no
                WHERE sub_o.is_cancelled = 0 AND sub_oi.quantity > 0
                GROUP BY sub_oi.stock_code
            )
        )
        ORDER BY "Product Revenue ($)" DESC
        LIMIT {limit};
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn)


def get_category_performance(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Advanced Query 5: Category-wise performance and sustainability distribution.
    """
    query = """
        SELECT 
            p.category AS "Category",
            COUNT(DISTINCT o.invoice_no) AS "Orders Count",
            SUM(oi.quantity) AS "Total Units Sold",
            ROUND(SUM(oi.total_price), 2) AS "Total Revenue ($)",
            ROUND(AVG(oi.unit_price), 2) AS "Avg Unit Price ($)",
            ROUND(SUM(CASE WHEN p.is_durable = 1 THEN oi.quantity ELSE 0 END) * 100.0 / SUM(oi.quantity), 1) AS "Durable Units Share (%)"
        FROM order_items oi
        JOIN products p ON oi.stock_code = p.stock_code
        JOIN orders o ON oi.invoice_no = o.invoice_no
        WHERE o.is_cancelled = 0 AND oi.quantity > 0
        GROUP BY p.category
        ORDER BY "Total Revenue ($)" DESC;
    """
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn)


def execute_custom_sql(query: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Executes an arbitrary SQL query safely (Read-Only enforcement for SELECT).
    Returns (DataFrame, error_message).
    """
    query_stripped = query.strip()
    if not query_stripped.upper().startswith("SELECT") and not query_stripped.upper().startswith("WITH"):
        return None, "Only SELECT or WITH queries are permitted in this runner."
    
    try:
        with get_connection(db_path) as conn:
            df = pd.read_sql_query(query, conn)
            return df, None
    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
    from data_cleaning import get_or_create_cleaned_data
    print("Loading cleaned dataset...")
    df_cleaned = get_or_create_cleaned_data()
    print("Populating SQLite database...")
    result = populate_database_from_df(df_cleaned)
    print("Populated records:", result)
    
    print("\n--- TEST QUERY 1: TOP 5 PRODUCTS BY REVENUE ---")
    print(get_top_5_products_by_revenue())
    
    print("\n--- TEST QUERY 2: MONTHLY REVENUE (GROUP BY) ---")
    print(get_monthly_revenue_summary().head())
    
    print("\n--- TEST QUERY 4: SUBQUERY ABOVE AVERAGE ---")
    print(get_products_exceeding_average_sales(limit=5))
