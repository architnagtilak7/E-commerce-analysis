"""
data_cleaning.py
================
High-Performance Data Cleaning and Preprocessing Pipeline for SDG E-commerce Analysis.
UCI Online Retail Dataset:
- Handles missing CustomerIDs and descriptions
- Identifies cancelled orders (InvoiceNo starting with 'C')
- Handles invalid/zero/negative quantities and unit prices
- Computes gross sales, returns, and net sales
- Maps products to sustainable retail categories and SDG eco-attributes
- Optimized with dictionary memoization on unique values for sub-second execution
"""

import os
import re
import pandas as pd
import numpy as np

# Category classification keyword maps for retail products
CATEGORY_KEYWORDS = {
    "Kitchenware & Dining": [
        "mug", "cup", "plate", "bowl", "fork", "spoon", "knife", "cutlery", "teapot",
        "biscuit tin", "tin", "baking", "cake", "pan", "bottle", "jug", "dish", "glass",
        "coaster", "serviette", "napkin", "lunch box", "flask", "jar", "salt", "pepper"
    ],
    "Home & Living": [
        "cushion", "doormat", "mat", "clock", "lantern", "candle", "nightlight", "drawer knob",
        "knob", "mirror", "frame", "photo frame", "hanger", "towel", "blanket", "rug",
        "curtain", "vase", "hook", "basket", "storage", "box", "bin", "cabinet", "shelf"
    ],
    "Stationery & Craft": [
        "notebook", "pocket book", "card", "greeting card", "pen", "pencil", "ruler",
        "eraser", "scissors", "tape", "ribbon", "wrap", "wrapping paper", "tissue", "tissues",
        "sticker", "craft", "feltcraft", "sewing", "needle", "stamp", "envelope", "chalk"
    ],
    "Toys & Games": [
        "game", "toy", "card game", "puzzle", "doll", "plush", "teddy", "play", "block",
        "yo-yo", "whistle", "balloon", "kite", "bubbles", "piggy bank"
    ],
    "Bags & Accessories": [
        "bag", "tote", "lunch bag", "shopper", "purse", "wallet", "pouch", "key fob",
        "keyring", "umbrella", "scarf", "gloves", "necklace", "bracelet", "earring", "jewellery"
    ],
    "Seasonal & Holiday": [
        "christmas", "xmas", "santa", "advent", "tree", "snow", "snowflake", "easter",
        "halloween", "heart", "valentine", "festive", "garland", "wreath", "bauble"
    ],
}

# Freight/Transport emission estimation zones (kg CO2e per order average)
# SDG 9 Infrastructure & Logistics analysis
LOGISTICS_ZONE_MAP = {
    "United Kingdom": {"zone": "UK Domestic", "freight_mode": "Electric/Diesel Van", "co2_factor_per_order": 0.45},
    "France": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.25},
    "Germany": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.35},
    "EIRE": {"zone": "Europe Regional", "freight_mode": "Ferry + Trucking", "co2_factor_per_order": 1.10},
    "Spain": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.80},
    "Netherlands": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.15},
    "Belgium": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.10},
    "Switzerland": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 1.50},
    "Portugal": {"zone": "Europe Regional", "freight_mode": "Cross-Border Trucking", "co2_factor_per_order": 2.10},
    "Australia": {"zone": "International Air", "freight_mode": "Long-Haul Air/Sea", "co2_factor_per_order": 8.50},
    "USA": {"zone": "International Air", "freight_mode": "Long-Haul Air/Sea", "co2_factor_per_order": 6.80},
    "Japan": {"zone": "International Air", "freight_mode": "Long-Haul Air/Sea", "co2_factor_per_order": 9.20},
}
DEFAULT_LOGISTICS = {"zone": "Europe Regional", "freight_mode": "Standard Freight", "co2_factor_per_order": 2.50}


# Flatten and sort all (keyword, category) by keyword length descending
# Ensures specific compound keywords (e.g. 'card game', 'biscuit tin') match before single words (e.g. 'card', 'tin')
SORTED_KEYWORD_RULES = []
for _cat, _kws in CATEGORY_KEYWORDS.items():
    for _kw in _kws:
        SORTED_KEYWORD_RULES.append((_kw, _cat))
SORTED_KEYWORD_RULES.sort(key=lambda item: len(item[0]), reverse=True)


def classify_category(description: str) -> str:
    """Classifies a single product description into a standard retail category."""
    if not isinstance(description, str) or not description.strip():
        return "Other / Miscellaneous"
    
    desc_lower = description.lower()
    for kw, category in SORTED_KEYWORD_RULES:
        if re.search(r'\b' + re.escape(kw) + r's?\b', desc_lower):
            return category
    return "Other / Miscellaneous"


def estimate_durability(category: str, description: str) -> bool:
    """Estimates if an item is durable (SDG 12.5) vs single-use."""
    desc_lower = str(description).lower()
    single_use_indicators = ["tissue", "wrap", "wrapping", "paper", "card", "napkin", "disposable", "sticker"]
    for ind in single_use_indicators:
        if ind in desc_lower:
            return False
    if category in ["Kitchenware & Dining", "Home & Living", "Bags & Accessories"]:
        return True
    return False


def get_logistics_meta(country: str) -> dict:
    """Returns shipping zone and emission profile for a given destination country."""
    if not isinstance(country, str):
        return DEFAULT_LOGISTICS
    return LOGISTICS_ZONE_MAP.get(country.strip(), DEFAULT_LOGISTICS)


def load_raw_dataset(filepath: str = "data/Online Retail.xlsx") -> pd.DataFrame:
    """Loads raw Excel dataset."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset file not found at: {filepath}")
    print(f"Reading raw Excel file '{filepath}'...", flush=True)
    df = pd.read_excel(filepath)
    print(f"Raw file loaded: {len(df):,} rows.", flush=True)
    return df


def clean_retail_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Comprehensive, high-performance data cleaning pipeline:
    1. Standardize column names
    2. Identify cancelled orders (InvoiceNo starts with 'C'/'c')
    3. Filter out system non-merchandise stock codes (POST, DOT, etc.)
    4. Handle missing descriptions (fill 'UNKNOWN PRODUCT')
    5. Handle CustomerID (fill 0 with IsGuest flag)
    6. Filter out invalid non-cancelled records with non-positive price or quantity
    7. Vectorized financial calculations (Sales, Gross Value)
    8. Fast dictionary mapping of unique descriptions to categories and eco-attributes
    9. Country and logistics emissions feature engineering
    """
    df = df.copy()
    
    # 1. Standardize column names
    df.columns = [c.strip() for c in df.columns]
    
    # 2. Identify cancellations
    df["InvoiceNo_str"] = df["InvoiceNo"].astype(str).str.strip()
    df["IsCancelled"] = df["InvoiceNo_str"].str.upper().str.startswith("C")
    
    # 3. Handle Descriptions
    df["Description"] = df["Description"].fillna("UNKNOWN PRODUCT")
    df["Description"] = df["Description"].astype(str).str.strip()
    df["Description"] = df["Description"].replace({
        "nan": "UNKNOWN PRODUCT",
        "None": "UNKNOWN PRODUCT",
        "": "UNKNOWN PRODUCT"
    })
    
    # Filter out system administrative records
    sys_stock_codes = {"POST", "D", "DOT", "M", "BANK CHARGES", "PADS", "CRUK"}
    df = df[~df["StockCode"].astype(str).str.strip().str.upper().isin(sys_stock_codes)]
    
    # 4. Handle CustomerID
    df["IsGuest"] = df["CustomerID"].isnull().astype(int)
    df["CustomerID"] = df["CustomerID"].fillna(0).astype(int)
    
    # 5. Handle UnitPrice and Quantity
    valid_cancelled = df["IsCancelled"] & (df["Quantity"] < 0) & (df["UnitPrice"] >= 0)
    valid_fulfilled = (~df["IsCancelled"]) & (df["Quantity"] > 0) & (df["UnitPrice"] > 0)
    df = df[valid_cancelled | valid_fulfilled].copy()
    
    # 6. Financial Calculations
    df["Sales"] = (df["Quantity"] * df["UnitPrice"]).round(2)
    df["ItemGrossValue"] = (df["Quantity"].abs() * df["UnitPrice"]).round(2)
    
    # 7. Date Handling
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Year"] = df["InvoiceDate"].dt.year
    df["Month"] = df["InvoiceDate"].dt.month
    df["YearMonth"] = df["InvoiceDate"].dt.strftime("%Y-%m")
    df["DayOfWeek"] = df["InvoiceDate"].dt.day_name()
    df["Hour"] = df["InvoiceDate"].dt.hour
    
    # 8. Country and Logistics (fast unique map)
    df["Country"] = df["Country"].astype(str).str.strip()
    unique_countries = df["Country"].unique()
    country_zone_map = {c: get_logistics_meta(c)["zone"] for c in unique_countries}
    country_co2_map = {c: get_logistics_meta(c)["co2_factor_per_order"] for c in unique_countries}
    df["LogisticsZone"] = df["Country"].map(country_zone_map)
    df["FreightCO2PerOrder"] = df["Country"].map(country_co2_map)
    
    # 9. Category & Eco Attributes (fast unique map - sub-second)
    unique_descs = df["Description"].unique()
    desc_cat_map = {d: classify_category(d) for d in unique_descs}
    desc_dur_map = {d: int(estimate_durability(desc_cat_map[d], d)) for d in unique_descs}
    
    df["Category"] = df["Description"].map(desc_cat_map)
    df["IsDurable"] = df["Description"].map(desc_dur_map)
    
    packaging_weights = {
        "Kitchenware & Dining": 85.0,
        "Home & Living": 110.0,
        "Stationery & Craft": 25.0,
        "Toys & Games": 60.0,
        "Bags & Accessories": 40.0,
        "Seasonal & Holiday": 45.0,
        "Other / Miscellaneous": 50.0,
    }
    df["EstPackagingGrams"] = df["Category"].map(packaging_weights).fillna(50.0) * df["Quantity"].abs()
    
    return df.reset_index(drop=True)


def get_or_create_cleaned_data(
    raw_path: str = "data/Online Retail.xlsx",
    clean_csv_path: str = "data/online_retail_cleaned.csv",
    force_rebuild: bool = False
) -> pd.DataFrame:
    """Loads cleaned CSV if present; otherwise processes Excel and caches CSV."""
    if os.path.exists(clean_csv_path) and not force_rebuild:
        df = pd.read_csv(clean_csv_path)
        df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
        return df
    
    raw_df = load_raw_dataset(raw_path)
    clean_df = clean_retail_data(raw_df)
    
    os.makedirs(os.path.dirname(clean_csv_path), exist_ok=True)
    clean_df.to_csv(clean_csv_path, index=False)
    print(f"Cleaned dataset saved successfully to: {clean_csv_path}", flush=True)
    return clean_df


if __name__ == "__main__":
    print("Executing Data Cleaning Pipeline...", flush=True)
    cleaned = get_or_create_cleaned_data()
    print(f"Cleaned Dataset Shape: {cleaned.shape}", flush=True)
    print("Columns:", list(cleaned.columns), flush=True)
    print("\nFulfilled vs Cancelled:")
    print(cleaned["IsCancelled"].value_counts())
    print("\nCategories distribution:")
    print(cleaned["Category"].value_counts())
