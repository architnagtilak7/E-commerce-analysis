"""
tests/test_sql_database.py
==========================
Pytest suite for SQLite database:
- Relational schema validation
- Ingestion pipeline
- Advanced SQL Queries:
  1. Top 5 products by revenue
  2. Monthly revenue using GROUP BY
  3. Multi-table SQL JOIN
  4. Subquery for above-average product sales
  5. Category-wise performance
- Safe query execution verification
"""

import os
import pytest
import pandas as pd
from sql_database import (
    init_database,
    populate_database_from_df,
    get_top_5_products_by_revenue,
    get_monthly_revenue_summary,
    get_joined_order_details,
    get_products_exceeding_average_sales,
    get_category_performance,
    execute_custom_sql
)
from data_cleaning import clean_retail_data

TEST_DB_PATH = "data/test_ecommerce.db"


@pytest.fixture(scope="module")
def setup_test_db():
    """Initializes and populates a test SQLite database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        
    # Create test transactions
    test_df = pd.DataFrame({
        "InvoiceNo": [1001, 1002, 1003, "C1004", 1005, 1006],
        "StockCode": ["P001", "P002", "P001", "P002", "P003", "P001"],
        "Description": [
            "CERAMIC TEAPOT",
            "METAL STORAGE BOX",
            "CERAMIC TEAPOT",
            "METAL STORAGE BOX",
            "GREETING CARD PACK",
            "CERAMIC TEAPOT"
        ],
        "Quantity": [5, 10, 8, -2, 20, 2],
        "InvoiceDate": pd.to_datetime([
            "2021-01-10 10:00:00",
            "2021-01-15 11:00:00",
            "2021-02-05 12:00:00",
            "2021-02-10 14:00:00",
            "2021-02-15 15:00:00",
            "2021-03-01 09:00:00"
        ]),
        "UnitPrice": [20.0, 15.0, 20.0, 15.0, 2.5, 20.0],
        "CustomerID": [101, 102, 101, 102, 103, 104],
        "Country": ["United Kingdom", "Germany", "United Kingdom", "Germany", "France", "United Kingdom"]
    })
    
    cleaned_df = clean_retail_data(test_df)
    counts = populate_database_from_df(cleaned_df, db_path=TEST_DB_PATH)
    yield counts
    
    # Teardown
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_schema_and_ingestion(setup_test_db):
    counts = setup_test_db
    assert counts["products"] == 3
    assert counts["customers"] == 4
    assert counts["orders"] == 6
    assert counts["order_items"] == 6


def test_top_products_query(setup_test_db):
    top_df = get_top_5_products_by_revenue(db_path=TEST_DB_PATH)
    assert not top_df.empty
    assert "Stock Code" in top_df.columns
    assert "Total Revenue ($)" in top_df.columns
    # P001 should be top (15 units * $20 = $300)
    top_code = top_df.iloc[0]["Stock Code"]
    assert top_code == "P001"


def test_monthly_group_by_query(setup_test_db):
    monthly_df = get_monthly_revenue_summary(db_path=TEST_DB_PATH)
    assert not monthly_df.empty
    assert "Month" in monthly_df.columns
    assert "Net Revenue ($)" in monthly_df.columns
    months = monthly_df["Month"].tolist()
    assert "2021-01" in months
    assert "2021-02" in months


def test_joined_query(setup_test_db):
    joined_df = get_joined_order_details(db_path=TEST_DB_PATH, limit=10)
    assert not joined_df.empty
    assert "Invoice No" in joined_df.columns
    assert "Description" in joined_df.columns
    assert "Country" in joined_df.columns


def test_subquery_above_average_sales(setup_test_db):
    sub_df = get_products_exceeding_average_sales(db_path=TEST_DB_PATH)
    assert not sub_df.empty
    assert "Catalog Avg Revenue ($)" in sub_df.columns
    # Check that each returned product's revenue exceeds catalog average
    for _, row in sub_df.iterrows():
        assert row["Product Revenue ($)"] > row["Catalog Avg Revenue ($)"]


def test_custom_sql_safety(setup_test_db):
    # Valid SELECT query should succeed
    df_valid, err = execute_custom_sql("SELECT count(*) as total FROM products", db_path=TEST_DB_PATH)
    assert err is None
    assert df_valid.iloc[0]["total"] == 3
    
    # Destructive non-SELECT query must be rejected
    df_invalid, err_reject = execute_custom_sql("DROP TABLE products", db_path=TEST_DB_PATH)
    assert df_invalid is None
    assert "Only SELECT or WITH" in err_reject
