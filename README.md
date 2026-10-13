# SDG in E-Commerce Analysis Dashboard
**DCDS Lab ESE Project · Data & Database Systems**

A complete, production-ready full-stack analytical platform analyzing online shopping data for sustainability insights aligned with **UN SDG 12 (Responsible Consumption & Production)** and **UN SDG 9 (Industry, Innovation & Infrastructure)**.

---

## 🚀 Key Highlights & Faculty Requirements

- **Dual-Database Integration**:
  - **SQLite (Relational SQL)**: 3NF Relational schema with `products`, `customers`, `orders`, and `order_items` tables storing structured transactions.
  - **MongoDB (NoSQL Document Store)**: Collections for `sdg_indicators`, `logistics_footprint`, and `sdg_recommendations`. Features a dual-mode engine that connects to live MongoDB (`localhost:27017`) or falls back to an embedded in-memory MongoDB engine (`mongomock`) with 100% PyMongo compatibility and descriptive status telemetry.
- **Advanced SQL Queries**:
  - Top 5 products by revenue (`JOIN` + `GROUP BY` + `ORDER BY`)
  - Monthly revenue trajectory (`GROUP BY` with conditional aggregation)
  - Multi-table SQL `JOIN` across orders, items, and products
  - Subquery identifying products exceeding catalog-wide average sales
  - Category-wise performance and durable circular goods ratio
- **MongoDB Aggregation Pipelines**:
  - Multi-stage pipelines utilizing `$match`, `$group`, `$sort`, `$project`.
- **Streamlit Multi-Page Interactive Dashboard**:
  - **Page 1: Commercial Overview**: Headline KPIs, monthly trends, top products by revenue.
  - **Page 2: Order & Cancellation Analysis**: Reverse logistics volume, cancellation drivers, purchasing timing.
  - **Page 3: SDG Sustainability Insights**: SDG 12 waste metrics & SDG 9 freight logistics carbon models.
  - **Page 4: Data Explorer & Live Queries**: Live SQL query runner + MongoDB aggregation runner + CSV export.
- **Automated Pytest Suite**: 22 unit tests passing with zero errors.

---

## 📁 Project Structure

```
sdg-ecommerce-analysis/
├── app.py                     # Streamlit multi-page interactive dashboard
├── data/
│   ├── Online Retail.xlsx     # Raw UCI Online Retail dataset (541K rows)
│   ├── online_retail_cleaned.csv # Cleaned, vectorized cached dataset (536K rows)
│   └── ecommerce.db           # SQLite 3NF relational database
├── data_cleaning.py           # Data preprocessing and feature engineering
├── sql_database.py            # SQLite schema, ingestion, and advanced SQL queries
├── mongodb_database.py        # MongoDB connection, ingestion & aggregation pipelines
├── analysis.py                # Commercial KPIs, SDG 12 & SDG 9 analytical models
├── requirements.txt           # Python dependencies
├── PROJECT_REPORT.md          # Comprehensive Lab ESE project report & query documentation
├── tests/
│   ├── test_data_cleaning.py  # Tests for null handling, cancellations, sales formula
│   ├── test_sql_database.py   # Tests for SQLite schema, ingestion & advanced queries
│   ├── test_mongodb_database.py # Tests for MongoDB connection & aggregations
│   └── test_analysis.py       # Tests for KPIs, SDG 12 & 9 calculations
└── README.md
```

---

## ⚡ Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Automated Tests
```bash
python -m pytest -v
```
*Expected: 22/22 tests passing.*

### 3. Launch the Dashboard
```bash
python -m streamlit run app.py
```
Open your browser and navigate to: **`http://localhost:8501`**

---

## 👥 Work Distribution (4 Members)

| Member | Primary Responsibility |
| :---: | :--- |
| **Member 1** | Dataset cleaning (`data_cleaning.py`) and SQLite relational schema (`sql_database.py`) |
| **Member 2** | Data analysis, headline KPIs, and SDG 12/9 mathematical indicators (`analysis.py`) |
| **Member 3** | Streamlit multi-page interactive dashboard, custom CSS, Plotly charts (`app.py`) |
| **Member 4** | MongoDB NoSQL integration, aggregation pipelines, and Pytest testing suite (`tests/`) |
