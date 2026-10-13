"""
tests/test_mongodb_database.py
==============================
Pytest suite for MongoDB integration:
- Dual-mode connection (Live or Embedded mongomock)
- Document insertion and retrieval
- Aggregation pipelines with stages: $match, $group, $sort, $project
- Custom pipeline runner validation
"""

import pytest
import json
from mongodb_database import (
    get_connection_status,
    populate_sdg_documents,
    aggregate_sdg_by_category,
    aggregate_logistics_footprint,
    aggregate_recommendations_by_sdg,
    execute_custom_mongo_pipeline
)

TEST_DB_NAME = "test_dcds_sdg"


@pytest.fixture(scope="module")
def seed_test_mongo():
    """Seeds test MongoDB documents."""
    categories = [
        {"category": "Kitchenware & Dining", "status": "active", "revenue": 1000.0, "return_rate_pct": 5.0, "cancelled_units": 10, "est_packaging_kg": 50.0, "durable_share_pct": 90.0},
        {"category": "Stationery & Craft", "status": "active", "revenue": 500.0, "return_rate_pct": 1.0, "cancelled_units": 2, "est_packaging_kg": 15.0, "durable_share_pct": 10.0},
        {"category": "Archived Category", "status": "inactive", "revenue": 200.0, "return_rate_pct": 0.0, "cancelled_units": 0, "est_packaging_kg": 5.0, "durable_share_pct": 0.0}
    ]
    logistics = [
        {"zone": "UK Domestic", "country": "United Kingdom", "order_count": 500, "total_co2_kg": 225.0, "avg_units_per_order": 12.0},
        {"zone": "Europe Regional", "country": "France", "order_count": 40, "total_co2_kg": 50.0, "avg_units_per_order": 15.0},
        {"zone": "International Air", "country": "Australia", "order_count": 5, "total_co2_kg": 42.5, "avg_units_per_order": 30.0}
    ]
    recs = [
        {"sdg_goal": "SDG 12", "title": "Packaging Reduction", "priority": "High", "potential_reduction_pct": 20.0},
        {"sdg_goal": "SDG 12", "title": "Return Waste Mitigation", "priority": "High", "potential_reduction_pct": 15.0},
        {"sdg_goal": "SDG 9", "title": "Regional Hub Deployment", "priority": "Medium", "potential_reduction_pct": 30.0}
    ]
    populate_sdg_documents(categories, logistics, recs, db_name=TEST_DB_NAME)
    return True


def test_connection_status():
    status = get_connection_status()
    assert status["connected"] is True
    assert status["mode"] in ["live", "embedded"]
    assert "dcds_ecommerce_sdg" in status["database"]


def test_aggregate_sdg_by_category(seed_test_mongo):
    results = aggregate_sdg_by_category(db_name=TEST_DB_NAME)
    assert len(results) == 2  # Only 2 'active' status categories, 'inactive' filtered out by $match
    # Ensure stages worked: sorted by packaging footprint descending
    assert results[0]["Category"] == "Kitchenware & Dining"
    assert "Revenue ($)" in results[0]
    assert "Avg Return Rate (%)" in results[0]


def test_aggregate_logistics_footprint(seed_test_mongo):
    results = aggregate_logistics_footprint(db_name=TEST_DB_NAME)
    assert len(results) == 3
    zones = [r["Logistics Zone"] for r in results]
    assert "UK Domestic" in zones
    assert "Europe Regional" in zones
    assert "International Air" in zones
    assert "Total Freight CO2 (kg)" in results[0]


def test_aggregate_recommendations_by_sdg(seed_test_mongo):
    results = aggregate_recommendations_by_sdg(db_name=TEST_DB_NAME)
    assert len(results) == 2
    sdg_goals = [r["SDG Goal"] for r in results]
    assert "SDG 12" in sdg_goals
    assert "SDG 9" in sdg_goals


def test_custom_mongo_pipeline_runner(seed_test_mongo):
    # Valid custom pipeline
    pipe_json = json.dumps([
        {"$match": {"priority": "High"}},
        {"$project": {"title": 1, "_id": 0}}
    ])
    results, err = execute_custom_mongo_pipeline("sdg_recommendations", pipe_json, db_name=TEST_DB_NAME)
    assert err is None
    assert len(results) == 2

    # Malformed JSON should return an error message
    bad_pipe = "{ invalid json }"
    bad_res, bad_err = execute_custom_mongo_pipeline("sdg_recommendations", bad_pipe, db_name=TEST_DB_NAME)
    assert bad_res is None
    assert bad_err is not None
