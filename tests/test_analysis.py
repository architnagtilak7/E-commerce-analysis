"""
tests/test_analysis.py
======================
Pytest suite for analytics engine:
- Commercial KPI computations
- Monthly trend calculations
- SDG 12 waste footprint and circularity metrics
- SDG 9 freight emissions calculations
"""

import pytest
import pandas as pd
from analysis import (
    get_overall_kpis,
    get_monthly_trends,
    get_top_products,
    get_cancellation_analysis,
    get_sdg12_metrics,
    get_sdg9_metrics
)
from data_cleaning import clean_retail_data


@pytest.fixture(scope="module")
def analysis_test_data():
    raw_df = pd.DataFrame({
        "InvoiceNo": [101, 102, "C103", 104],
        "StockCode": ["P1", "P2", "P1", "P3"],
        "Description": ["CERAMIC BOWL", "TISSUE PACK", "CERAMIC BOWL", "METAL TOOLBOX"],
        "Quantity": [10, 5, -2, 4],
        "InvoiceDate": pd.to_datetime(["2021-01-01", "2021-01-15", "2021-02-01", "2021-02-20"]),
        "UnitPrice": [10.0, 2.0, 10.0, 25.0],
        "CustomerID": [2001, 2002, 2001, 2003],
        "Country": ["United Kingdom", "United Kingdom", "United Kingdom", "Australia"]
    })
    return clean_retail_data(raw_df)


def test_headline_kpis(analysis_test_data):
    kpis = get_overall_kpis(analysis_test_data)
    # Fulfilled: 10*10 + 5*2 + 4*25 = 100 + 10 + 100 = 210
    # Refunds: 2*10 = 20
    # Net: 210 - 20 = 190
    assert kpis["gross_revenue"] == 210.0
    assert kpis["refund_amount"] == 20.0
    assert kpis["net_revenue"] == 190.0
    assert kpis["total_orders"] == 4
    assert kpis["fulfilled_orders"] == 3
    assert kpis["cancelled_orders"] == 1
    assert kpis["cancellation_rate_pct"] == 25.0


def test_monthly_trends(analysis_test_data):
    monthly = get_monthly_trends(analysis_test_data)
    assert len(monthly) == 2
    assert "2021-01" in monthly["YearMonth"].values
    assert "2021-02" in monthly["YearMonth"].values


def test_sdg12_metrics(analysis_test_data):
    sdg12 = get_sdg12_metrics(analysis_test_data)
    assert sdg12["returned_units"] == 2
    assert sdg12["wasted_packaging_kg"] > 0
    assert len(sdg12["recommendations"]) == 3
    assert any(r["sdg_goal"] == "SDG 12" for r in sdg12["recommendations"])


def test_sdg9_metrics(analysis_test_data):
    sdg9 = get_sdg9_metrics(analysis_test_data)
    assert sdg9["total_co2_kg"] > 0
    assert len(sdg9["zone_summary"]) >= 2
    zones = sdg9["zone_summary"]["LogisticsZone"].tolist()
    assert "UK Domestic" in zones
    assert "International Air" in zones
    assert len(sdg9["recommendations"]) == 3
