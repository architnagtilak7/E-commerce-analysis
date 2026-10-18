"""
migrate_to_atlas.py
===================
Standalone MongoDB Atlas Migration & Seeding Utility.
Reads MONGODB_URI from .env (or command line) and seeds all collections:
- sdg_indicators
- logistics_footprint
- sdg_recommendations
Then verifies connection and runs sample aggregation pipelines.
"""

import os
import sys
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

from data_cleaning import get_or_create_cleaned_data
from analysis import sync_analytics_to_mongodb
from mongodb_database import (
    get_connection_status,
    aggregate_sdg_by_category,
    aggregate_logistics_footprint,
    aggregate_recommendations_by_sdg,
    mask_mongo_uri,
    reset_mongo_connection
)


def run_migration():
    print("=" * 60)
    print("🌱 MongoDB Atlas Migration & Verification Engine")
    print("=" * 60)
    
    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        print("❌ Error: MONGODB_URI not found in environment or .env file.")
        print("Please set MONGODB_URI in your .env file or environment.")
        sys.exit(1)
        
    print(f"Target MongoDB URI: {mask_mongo_uri(uri)}")
    
    reset_mongo_connection()
    status = get_connection_status()
    print(f"Engine Mode: {status['mode'].upper()}")
    print(f"Status Diagnostic: {status['message']}")
    
    print("\n1. Loading Cleaned Dataset...")
    df = get_or_create_cleaned_data()
    print(f"Dataset ready: {len(df):,} records.")
    
    print("\n2. Seeding Collections to MongoDB...")
    seed_result = sync_analytics_to_mongodb(df)
    for col, count in seed_result.items():
        print(f"   ✓ Seeded '{col}': {count} documents")
        
    print("\n3. Testing MongoDB Aggregation Pipelines on Seeded Data...")
    cat_agg = aggregate_sdg_by_category()
    print(f"   ✓ Aggregation 1 (SDG by Category): {len(cat_agg)} categories grouped ($match, $group, $sort, $project)")
    
    log_agg = aggregate_logistics_footprint()
    print(f"   ✓ Aggregation 2 (Logistics Emissions): {len(log_agg)} zones grouped ($match, $group, $sort, $project)")
    
    rec_agg = aggregate_recommendations_by_sdg()
    print(f"   ✓ Aggregation 3 (SDG Recommendations): {len(rec_agg)} goals grouped ($match, $group, $sort, $project)")
    
    print("\n" + "=" * 60)
    print("🎉 Migration & Verification Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
