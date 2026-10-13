"""
tests/test_data_cleaning.py
===========================
Pytest suite for data cleaning pipeline:
- Missing customer handling
- Cancellation detection ('C' prefix)
- Invalid prices/quantities
- Financial calculations (Sales = Quantity * UnitPrice)
- Category classification & durability tagging
"""

import pytest
import pandas as pd
import numpy as np
from data_cleaning import clean_retail_data, classify_category, estimate_durability


@pytest.fixture
def sample_raw_data():
    """Generates a representative sample of raw retail transactions."""
    return pd.DataFrame({
        "InvoiceNo": [536365, "C536379", 536366, 536367, "C536380", 536368, 536369],
        "StockCode": ["85123A", "D", "POST", "22423", "22423", "84029G", "84029E"],
        "Description": [
            "WHITE HANGING HEART T-LIGHT HOLDER",
            "Discount adjustment",
            "POSTAGE",
            "REGENCY CAKESTAND 3 TIER",
            "REGENCY CAKESTAND 3 TIER",
            None,
            "PACK OF 12 LONDON TISSUES"
        ],
        "Quantity": [6, -1, 1, 10, -2, 4, 12],
        "InvoiceDate": pd.to_datetime([
            "2010-12-01 08:26:00",
            "2010-12-01 09:41:00",
            "2010-12-01 09:45:00",
            "2010-12-01 10:00:00",
            "2010-12-01 10:30:00",
            "2010-12-01 11:00:00",
            "2010-12-01 11:30:00"
        ]),
        "UnitPrice": [2.55, 27.50, 18.00, 12.75, 12.75, 3.75, 0.85],
        "CustomerID": [17850, 14096, 17850, 15311, 15311, np.nan, 13047],
        "Country": ["United Kingdom", "United Kingdom", "United Kingdom", "Germany", "Germany", "United Kingdom", "France"]
    })


def test_cancellation_detection(sample_raw_data):
    cleaned = clean_retail_data(sample_raw_data)
    # C536380 should be identified as cancelled (C536379 had StockCode 'D' which is filtered out)
    cancelled_invoices = cleaned[cleaned["IsCancelled"]]["InvoiceNo_str"].tolist()
    assert "C536380" in cancelled_invoices
    assert all(inv.startswith("C") for inv in cancelled_invoices)


def test_system_code_filtering(sample_raw_data):
    cleaned = clean_retail_data(sample_raw_data)
    # 'D' and 'POST' must be filtered out
    stock_codes = cleaned["StockCode"].tolist()
    assert "D" not in stock_codes
    assert "POST" not in stock_codes


def test_missing_customer_handling(sample_raw_data):
    cleaned = clean_retail_data(sample_raw_data)
    # Missing CustomerID must be mapped to 0 with IsGuest flag = 1
    guest_rows = cleaned[cleaned["IsGuest"] == 1]
    assert len(guest_rows) == 1
    assert guest_rows.iloc[0]["CustomerID"] == 0


def test_missing_description_handling(sample_raw_data):
    cleaned = clean_retail_data(sample_raw_data)
    # None description should be filled with UNKNOWN PRODUCT
    unknown_desc_rows = cleaned[cleaned["Description"] == "UNKNOWN PRODUCT"]
    assert len(unknown_desc_rows) == 1


def test_financial_calculations(sample_raw_data):
    cleaned = clean_retail_data(sample_raw_data)
    # Check fulfilled order: 6 * 2.55 = 15.30
    row_first = cleaned[cleaned["InvoiceNo_str"] == "536365"].iloc[0]
    assert pytest.approx(row_first["Sales"], 0.01) == 15.30
    
    # Check cancelled order: -2 * 12.75 = -25.50
    row_canc = cleaned[cleaned["InvoiceNo_str"] == "C536380"].iloc[0]
    assert pytest.approx(row_canc["Sales"], 0.01) == -25.50
    assert pytest.approx(row_canc["ItemGrossValue"], 0.01) == 25.50


def test_category_classification():
    assert classify_category("RED SPOTTY BISCUIT TIN") == "Kitchenware & Dining"
    assert classify_category("WHITE SPOT RED CERAMIC DRAWER KNOB") == "Home & Living"
    assert classify_category("SET OF 3 NOTEBOOKS IN PARCEL") == "Stationery & Craft"
    assert classify_category("VINTAGE HEADS AND TAILS CARD GAME") == "Toys & Games"
    assert classify_category("LUNCH BAG RED RETROSPOT") == "Bags & Accessories"
    assert classify_category("CHRISTMAS TREE DECORATION") == "Seasonal & Holiday"
    assert classify_category("UNKNOWN XYZ ITEM") == "Other / Miscellaneous"


def test_durability_estimation():
    # Kitchenware & Home are durable
    assert estimate_durability("Kitchenware & Dining", "CERAMIC MUG") is True
    # Disposable items (tissues, wrap, cards) are single-use
    assert estimate_durability("Stationery & Craft", "PACK OF 12 LONDON TISSUES") is False
    assert estimate_durability("Stationery & Craft", "CHRISTMAS WRAPPING PAPER") is False
