"""
app.py
======
SDG in E-Commerce Analysis Dashboard
Comprehensive interactive platform for DCDS Lab ESE.
Integrates:
- Streamlit multi-page interface with rich UI aesthetics
- SQLite relational database & advanced SQL queries
- MongoDB NoSQL database & aggregation pipelines ($match, $group, $sort, $project)
- SDG 12 (Responsible Consumption & Production) & SDG 9 (Industry, Innovation & Infrastructure)
"""

import os
import json
import time
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_cleaning import get_or_create_cleaned_data
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
    execute_custom_mongo_pipeline
)
from analysis import (
    get_overall_kpis,
    get_monthly_trends,
    get_top_products,
    get_cancellation_analysis,
    get_sdg12_metrics,
    get_sdg9_metrics,
    sync_analytics_to_mongodb
)

# Page configuration
st.set_page_config(
    page_title="SDG E-Commerce Sustainability Hub",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for polished visual presentation
st.markdown("""
<style>
    /* Metric Card Styling */
    .metric-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        margin-bottom: 12px;
    }
    .metric-title {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #0284c7;
        margin-bottom: 2px;
    }
    .metric-sub {
        font-size: 0.78rem;
        color: #64748b;
    }
    /* Status Badges */
    .badge-sql {
        background-color: #0284c7;
        color: white;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-mongo {
        background-color: #10b981;
        color: white;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .sdg-badge-12 {
        background: #cf8d2e;
        color: white;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .sdg-badge-9 {
        background: #f15e3a;
        color: white;
        padding: 4px 10px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_and_prepare_data():
    """Caches cleaned data and ensures databases are seeded."""
    df = get_or_create_cleaned_data()
    # Synchronize MongoDB collections
    sync_analytics_to_mongodb(df)
    return df


# Load data
with st.spinner("Initializing analytics engine and database connectors..."):
    df_raw = load_and_prepare_data()

# =========================================================================
# SIDEBAR FILTERS & DATABASE TELEMETRY
# =========================================================================

st.sidebar.markdown("### 🌱 SDG Analytics Hub")
st.sidebar.caption("DCDS Lab ESE Project · Online Shopping Sustainability")

# Navigation Menu
nav_page = st.sidebar.radio(
    "Go to Navigation Page:",
    [
        "📊 Page 1: Commercial Overview",
        "📦 Page 2: Order & Cancellation Analysis",
        "🌍 Page 3: SDG Sustainability Insights",
        "⚡ Page 4: Data Explorer & Live Queries"
    ],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Global Filter Controls")

# Date range filter
min_date = df_raw["InvoiceDate"].min().date()
max_date = df_raw["InvoiceDate"].max().date()

date_range = st.sidebar.date_input(
    "Filter Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Country filter
all_countries = ["All Countries"] + sorted(df_raw["Country"].unique().tolist())
selected_country = st.sidebar.selectbox("Filter by Country:", all_countries, index=0)

# Category filter
all_categories = ["All Categories"] + sorted(df_raw["Category"].unique().tolist())
selected_category = st.sidebar.selectbox("Filter by Retail Category:", all_categories, index=0)

# Order Status filter
status_filter = st.sidebar.radio(
    "Filter Order Status:",
    ["All Orders", "Fulfilled Only", "Cancelled / Returns Only"],
    index=0
)

# Apply Filters
filtered_df = df_raw.copy()

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_d, end_d = date_range
    filtered_df = filtered_df[
        (filtered_df["InvoiceDate"].dt.date >= start_d) &
        (filtered_df["InvoiceDate"].dt.date <= end_d)
    ]

if selected_country != "All Countries":
    filtered_df = filtered_df[filtered_df["Country"] == selected_country]

if selected_category != "All Categories":
    filtered_df = filtered_df[filtered_df["Category"] == selected_category]

if status_filter == "Fulfilled Only":
    filtered_df = filtered_df[~filtered_df["IsCancelled"]]
elif status_filter == "Cancelled / Returns Only":
    filtered_df = filtered_df[filtered_df["IsCancelled"]]

# Database Health Card in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("🔌 Database Connections")

# SQLite status
if os.path.exists(DEFAULT_DB_PATH):
    st.sidebar.markdown('<span class="badge-sql">SQLITE: ACTIVE</span> `ecommerce.db`', unsafe_allow_html=True)
else:
    st.sidebar.error("SQLite database not found at data/ecommerce.db")

# MongoDB status
mongo_stat = get_connection_status()
if mongo_stat["mode"] == "live":
    st.sidebar.markdown('<span class="badge-mongo">MONGODB: LIVE</span> `localhost:27017`', unsafe_allow_html=True)
else:
    st.sidebar.markdown('<span class="badge-mongo">MONGODB: EMBEDDED</span> `mongomock engine`', unsafe_allow_html=True)
    st.sidebar.caption("⚡ Live MongoDB fallback active with 100% PyMongo compatibility.")


# =========================================================================
# PAGE 1: OVERVIEW
# =========================================================================
if nav_page == "📊 Page 1: Commercial Overview":
    st.title("📊 Commercial & Sales Overview")
    st.markdown("High-level revenue telemetry, order velocity, and top merchandise demand.")
    
    kpis = get_overall_kpis(filtered_df)
    
    # KPI Row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Gross Revenue</div>
            <div class="metric-value">${kpis['gross_revenue']:,.0f}</div>
            <div class="metric-sub">Fulfilled order volume</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Net Sales</div>
            <div class="metric-value" style="color: #10b981;">${kpis['net_revenue']:,.0f}</div>
            <div class="metric-sub">After -${kpis['refund_amount']:,.0f} refunds</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Orders</div>
            <div class="metric-value" style="color: #6366f1;">{kpis['total_orders']:,}</div>
            <div class="metric-sub">{kpis['fulfilled_orders']:,} fulfilled | {kpis['cancelled_orders']:,} ret</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Units Sold</div>
            <div class="metric-value" style="color: #f59e0b;">{kpis['total_units_sold']:,}</div>
            <div class="metric-sub">AOV: ${kpis['avg_order_value']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Customer Reach</div>
            <div class="metric-value" style="color: #8b5cf6;">{kpis['unique_customers']:,}</div>
            <div class="metric-sub">{kpis['guest_ratio_pct']}% guest checkouts</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    # Charts: Monthly Trends & Top Products
    row1_col1, row1_col2 = st.columns([3, 2])
    
    with row1_col1:
        st.subheader("📈 Monthly Revenue & Refund Trajectory")
        monthly_df = get_monthly_trends(filtered_df)
        if not monthly_df.empty:
            fig_monthly = go.Figure()
            fig_monthly.add_trace(go.Bar(
                x=monthly_df["YearMonth"],
                y=monthly_df["fulfilled_revenue"],
                name="Gross Sales ($)",
                marker_color="#0284c7"
            ))
            fig_monthly.add_trace(go.Bar(
                x=monthly_df["YearMonth"],
                y=monthly_df["refund_amount"],
                name="Returned Value ($)",
                marker_color="#ef4444"
            ))
            fig_monthly.add_trace(go.Scatter(
                x=monthly_df["YearMonth"],
                y=monthly_df["net_revenue"],
                name="Net Revenue ($)",
                mode="lines+markers",
                line=dict(color="#10b981", width=3)
            ))
            fig_monthly.update_layout(
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=30, b=20),
                height=380
            )
            st.plotly_chart(fig_monthly, use_container_width=True)
        else:
            st.info("No transaction data available for the chosen filters.")
            
    with row1_col2:
        st.subheader("🏆 Top Products by Revenue")
        top_prod_df = get_top_products(filtered_df, n=8, by="revenue")
        if not top_prod_df.empty:
            fig_top = px.bar(
                top_prod_df,
                x="revenue",
                y="Description",
                orientation="h",
                color="Category",
                title=None,
                labels={"revenue": "Revenue ($)", "Description": "Product"}
            )
            fig_top.update_layout(
                yaxis=dict(autorange="reversed"),
                margin=dict(l=20, r=20, t=30, b=20),
                height=380
            )
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("No products match the selected criteria.")

    # Category Share & Global Geography
    row2_col1, row2_col2 = st.columns([1, 1])
    
    with row2_col1:
        st.subheader("🛍️ Revenue Distribution by Product Category")
        cat_rev = filtered_df[~filtered_df["IsCancelled"]].groupby("Category")["Sales"].sum().reset_index()
        fig_donut = px.pie(
            cat_rev,
            names="Category",
            values="Sales",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_donut.update_traces(textposition='inside', textinfo='percent+label')
        fig_donut.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=340)
        st.plotly_chart(fig_donut, use_container_width=True)

    with row2_col2:
        st.subheader("🌐 Top 8 Markets by Gross Revenue")
        country_rev = (
            filtered_df[~filtered_df["IsCancelled"]]
            .groupby("Country")["Sales"]
            .sum()
            .reset_index()
            .sort_values("Sales", ascending=False)
            .head(8)
        )
        fig_country = px.bar(
            country_rev,
            x="Country",
            y="Sales",
            color="Sales",
            color_continuous_scale="Viridis",
            labels={"Sales": "Gross Sales ($)"}
        )
        fig_country.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=340)
        st.plotly_chart(fig_country, use_container_width=True)


# =========================================================================
# PAGE 2: ORDER & CANCELLATION ANALYSIS
# =========================================================================
elif nav_page == "📦 Page 2: Order & Cancellation Analysis":
    st.title("📦 Order & Cancellation Deep-Dive")
    st.markdown("Identify cancellation drivers, reverse logistics returns, and purchasing timing trends.")
    
    canc_data = get_cancellation_analysis(filtered_df)
    kpis = get_overall_kpis(filtered_df)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Cancellation Rate</div>
            <div class="metric-value" style="color: #ef4444;">{kpis['cancellation_rate_pct']}%</div>
            <div class="metric-sub">{kpis['cancelled_orders']:,} cancelled / returned invoices</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Returned Units Volume</div>
            <div class="metric-value" style="color: #f97316;">{kpis['total_units_returned']:,}</div>
            <div class="metric-sub">Items processed via reverse logistics</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Financial Refund Impact</div>
            <div class="metric-value" style="color: #dc2626;">${kpis['refund_amount']:,.2f}</div>
            <div class="metric-sub">Revenue lost from returns & cancellations</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs([
        "🚨 High-Return Products (Waste Hotspots)",
        "🗺️ Country Cancellation Rates",
        "⏰ Purchasing Trends (Day & Hour)"
    ])
    
    with tab1:
        st.subheader("Top Products Driving Reverse Logistics Volume")
        st.caption("Products with the highest returned quantities directly increase logistics carbon and packaging scrap.")
        top_ret_df = canc_data["top_returned_products"]
        if not top_ret_df.empty:
            col_t1, col_t2 = st.columns([3, 2])
            with col_t1:
                fig_ret = px.bar(
                    top_ret_df,
                    x="returned_quantity",
                    y="Description",
                    orientation="h",
                    color="Category",
                    labels={"returned_quantity": "Units Returned", "Description": "Product"}
                )
                fig_ret.update_layout(yaxis=dict(autorange="reversed"), height=380)
                st.plotly_chart(fig_ret, use_container_width=True)
            with col_t2:
                st.dataframe(
                    top_ret_df[[
                        "StockCode", "Description", "returned_quantity", "returned_value"
                    ]].rename(columns={
                        "StockCode": "Code",
                        "returned_quantity": "Qty Returned",
                        "returned_value": "Refund ($)"
                    }),
                    use_container_width=True,
                    height=380
                )
        else:
            st.info("No cancellation records match the filter criteria.")

    with tab2:
        st.subheader("Cancellation Frequency Across Major Markets")
        country_rates = canc_data["country_cancellation_rates"]
        if not country_rates.empty:
            fig_crate = px.bar(
                country_rates.head(15),
                x="Country",
                y="Cancellation Rate (%)",
                color="Cancellation Rate (%)",
                color_continuous_scale="Reds",
                text="Cancellation Rate (%)"
            )
            fig_crate.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_crate.update_layout(height=400, margin=dict(t=20, b=20))
            st.plotly_chart(fig_crate, use_container_width=True)
        else:
            st.info("Insufficient order count per country for percentage calculation.")

    with tab3:
        st.subheader("Order Placement by Day of Week & Hour")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            day_df = canc_data["day_pattern"]
            fig_day = go.Figure()
            if False in day_df.columns:
                fig_day.add_trace(go.Bar(x=day_df["DayOfWeek"], y=day_df[False], name="Fulfilled Orders", marker_color="#0284c7"))
            if True in day_df.columns:
                fig_day.add_trace(go.Bar(x=day_df["DayOfWeek"], y=day_df[True], name="Cancelled Orders", marker_color="#ef4444"))
            fig_day.update_layout(barmode="stack", title="Order Volume by Day of Week", height=350)
            st.plotly_chart(fig_day, use_container_width=True)
            
        with col_d2:
            hour_df = filtered_df.groupby(["Hour", "IsCancelled"])["InvoiceNo_str"].nunique().unstack(fill_value=0).reset_index()
            fig_hour = px.line(
                hour_df,
                x="Hour",
                y=hour_df.columns[1:],
                title="Hourly Order Traffic",
                labels={"value": "Order Invoices", "Hour": "Hour of Day (24h)"}
            )
            fig_hour.update_layout(height=350)
            st.plotly_chart(fig_hour, use_container_width=True)


# =========================================================================
# PAGE 3: SDG INSIGHTS (SDG 12 & SDG 9)
# =========================================================================
elif nav_page == "🌍 Page 3: SDG Sustainability Insights":
    st.title("🌍 UN Sustainable Development Goals Insights")
    st.markdown("Measuring environmental impact and driving sustainable retail practices under **SDG 12** and **SDG 9**.")
    
    sdg12 = get_sdg12_metrics(filtered_df)
    sdg9 = get_sdg9_metrics(filtered_df)
    
    tab_sdg12, tab_sdg9 = st.tabs([
        "🌱 SDG 12: Responsible Consumption & Production",
        "🏗️ SDG 9: Industry, Innovation & Infrastructure"
    ])
    
    with tab_sdg12:
        st.markdown("""
        ### <span class="sdg-badge-12">SDG 12</span> Responsible Consumption and Production
        **Target 12.5**: Substantially reduce waste generation through prevention, reduction, recycling, and reuse.
        """, unsafe_allow_html=True)
        
        # SDG 12 KPI Scorecard
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Reverse Logistics Waste</div>
                <div class="metric-value" style="color: #dc2626;">{sdg12['returned_units']:,}</div>
                <div class="metric-sub">Units returned generating excess scrap</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Return Packaging Scrap</div>
                <div class="metric-value" style="color: #f97316;">{sdg12['wasted_packaging_kg']:,.1f} kg</div>
                <div class="metric-sub">Wasted cardboard & void-fill material</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Durable Goods Ratio</div>
                <div class="metric-value" style="color: #10b981;">{sdg12['durable_ratio_pct']}%</div>
                <div class="metric-sub">Long-life vs single-use units sold</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total Packaging Mass</div>
                <div class="metric-value" style="color: #0284c7;">{sdg12['fulfilled_packaging_kg']:,.0f} kg</div>
                <div class="metric-sub">Estimated fulfilled packaging footprint</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # Category Packaging Footprint Chart
        c1, c2 = st.columns([3, 2])
        with c1:
            st.subheader("📦 Estimated Packaging Material Intensity by Category")
            cat_metrics = sdg12["category_metrics"]
            fig_pack = px.bar(
                cat_metrics,
                x="Category",
                y="packaging_kg",
                color="durable_share_pct",
                color_continuous_scale="Teal",
                labels={"packaging_kg": "Packaging Mass (kg)", "durable_share_pct": "Durable %"}
            )
            fig_pack.update_layout(height=360)
            st.plotly_chart(fig_pack, use_container_width=True)
            
        with c2:
            st.subheader("♻️ Circular Economy Durability Share")
            fig_circ = px.pie(
                names=["Durable / Reusable", "Single-Use / Ephemeral"],
                values=[sdg12["durable_ratio_pct"], round(100 - sdg12["durable_ratio_pct"], 1)],
                color_discrete_sequence=["#10b981", "#cbd5e1"],
                hole=0.6
            )
            fig_circ.update_layout(height=360, margin=dict(t=20, b=20))
            st.plotly_chart(fig_circ, use_container_width=True)

        st.subheader("💡 SDG 12 Actionable Recommendations (Data-Backed)")
        for rec in sdg12["recommendations"]:
            with st.expander(f"📌 {rec['title']} [{rec['priority']} Priority]"):
                st.markdown(f"**Target:** {rec['target']} | **Timeline:** {rec['timeline']}")
                st.write(rec['description'])
                st.success(f"🎯 **Projected Waste Reduction:** {rec['potential_reduction_pct']}% in {rec['metric']}")

    with tab_sdg9:
        st.markdown("""
        ### <span class="sdg-badge-9">SDG 9</span> Industry, Innovation, and Infrastructure
        **Target 9.4**: Retrofit industries and freight transport to make them sustainable, with increased resource-use efficiency.
        """, unsafe_allow_html=True)
        
        # SDG 9 KPI Scorecard
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Freight Logistics Carbon</div>
                <div class="metric-value" style="color: #f15e3a;">{sdg9['total_co2_kg']:,.1f} kg</div>
                <div class="metric-sub">Total estimated transport CO₂ equivalent</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Domestic UK Share</div>
                <div class="metric-value" style="color: #0284c7;">
                    {sdg9['zone_summary'][sdg9['zone_summary']['LogisticsZone'] == 'UK Domestic']['total_co2_kg'].values[0] if 'UK Domestic' in sdg9['zone_summary']['LogisticsZone'].values else 0:,.0f} kg
                </div>
                <div class="metric-sub">Ground distribution courier footprint</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Cross-Border / Air Share</div>
                <div class="metric-value" style="color: #dc2626;">
                    {sdg9['zone_summary'][sdg9['zone_summary']['LogisticsZone'] != 'UK Domestic']['total_co2_kg'].sum():,.0f} kg
                </div>
                <div class="metric-sub">High-intensity long haul transport</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        
        # Zone breakdown & Route batching
        col_z1, col_z2 = st.columns(2)
        with col_z1:
            st.subheader("🚚 Freight CO₂ Footprint by Logistics Zone")
            fig_zone = px.bar(
                sdg9["zone_summary"],
                x="LogisticsZone",
                y="total_co2_kg",
                color="co2_intensity_per_100_usd",
                color_continuous_scale="Reds",
                labels={"total_co2_kg": "CO₂ Emissions (kg)", "co2_intensity_per_100_usd": "CO₂ / $100 Revenue"}
            )
            fig_zone.update_layout(height=360)
            st.plotly_chart(fig_zone, use_container_width=True)
            
        with col_z2:
            st.subheader("📦 Order Batching Efficiency (Units per Shipment)")
            st.caption("Higher units per order lowers per-item freight emissions.")
            fig_batch = px.bar(
                sdg9["zone_summary"],
                x="LogisticsZone",
                y="avg_units_per_order",
                color="LogisticsZone",
                labels={"avg_units_per_order": "Avg Units / Order"}
            )
            fig_batch.update_layout(height=360)
            st.plotly_chart(fig_batch, use_container_width=True)

        st.subheader("💡 SDG 9 Actionable Logistics Recommendations")
        for rec in sdg9["recommendations"]:
            with st.expander(f"🚛 {rec['title']} [{rec['priority']} Priority]"):
                st.markdown(f"**Target:** {rec['target']} | **Timeline:** {rec['timeline']}")
                st.write(rec['description'])
                st.success(f"🎯 **Projected Carbon Reduction:** {rec['potential_reduction_pct']}% in {rec['metric']}")


# =========================================================================
# PAGE 4: DATA EXPLORER & ADVANCED QUERIES
# =========================================================================
elif nav_page == "⚡ Page 4: Data Explorer & Live Queries":
    st.title("⚡ Data Explorer & Advanced Database Queries")
    st.markdown("Inspect cleaned data, run advanced **SQL Relational Queries**, and execute **MongoDB NoSQL Aggregations**.")
    
    tab_sql, tab_mongo, tab_data = st.tabs([
        "🗄️ SQL Advanced Queries (SQLite)",
        "🍃 MongoDB Aggregation Pipeline ($match, $group, etc.)",
        "📋 Cleaned Data Explorer & Export"
    ])
    
    # ------------------ SQL TAB ------------------
    with tab_sql:
        st.subheader("Advanced SQL Relational Queries")
        st.markdown("Select from faculty-required advanced SQL query templates or compose custom SQL.")
        
        query_options = {
            "1. Top 5 Products by Revenue (JOIN + GROUP BY + ORDER BY)": "top5",
            "2. Monthly Revenue Trends (GROUP BY + Aggregate CASE)": "monthly",
            "3. Multi-Table JOIN (Orders ↔ Order_Items ↔ Products)": "join",
            "4. Subquery: Products Exceeding Average Sales across Catalog": "subquery",
            "5. Category Performance & Durable Eco Ratio": "category",
            "Custom SQL Query": "custom"
        }
        
        selected_sql_key = st.selectbox("Select SQL Query to Execute:", list(query_options.keys()))
        sql_choice = query_options[selected_sql_key]
        
        if sql_choice == "top5":
            st.code("""
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
            """, language="sql")
            t0 = time.time()
            res_df = get_top_5_products_by_revenue()
            st.success(f"Executed successfully in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(res_df, use_container_width=True)

        elif sql_choice == "monthly":
            st.code("""
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
            """, language="sql")
            t0 = time.time()
            res_df = get_monthly_revenue_summary()
            st.success(f"Executed successfully in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(res_df, use_container_width=True)

        elif sql_choice == "join":
            st.code("""
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
LIMIT 15;
            """, language="sql")
            t0 = time.time()
            res_df = get_joined_order_details(limit=15)
            st.success(f"Executed successfully in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(res_df, use_container_width=True)

        elif sql_choice == "subquery":
            st.code("""
SELECT 
    p.stock_code AS "Stock Code",
    p.description AS "Description",
    p.category AS "Category",
    SUM(oi.quantity) AS "Total Quantity",
    ROUND(SUM(oi.total_price), 2) AS "Product Revenue ($)",
    ROUND((SELECT AVG(sub_revenue) FROM (
        SELECT SUM(sub_oi.total_price) AS sub_revenue
        FROM order_items sub_oi
        JOIN orders sub_o ON sub_oi.invoice_no = sub_o.invoice_no
        WHERE sub_o.is_cancelled = 0 AND sub_oi.quantity > 0
        GROUP BY sub_oi.stock_code
    )), 2) AS "Catalog Avg Revenue ($)"
FROM order_items oi
JOIN products p ON oi.stock_code = p.stock_code
JOIN orders o ON oi.invoice_no = o.invoice_no
WHERE o.is_cancelled = 0 AND oi.quantity > 0
GROUP BY p.stock_code, p.description, p.category
HAVING SUM(oi.total_price) > (
    SELECT AVG(sub_revenue) FROM (
        SELECT SUM(sub_oi.total_price) AS sub_revenue
        FROM order_items sub_oi
        JOIN orders sub_o ON sub_oi.invoice_no = sub_o.invoice_no
        WHERE sub_o.is_cancelled = 0 AND sub_oi.quantity > 0
        GROUP BY sub_oi.stock_code
    )
)
ORDER BY "Product Revenue ($)" DESC
LIMIT 10;
            """, language="sql")
            t0 = time.time()
            res_df = get_products_exceeding_average_sales(limit=10)
            st.success(f"Executed successfully in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(res_df, use_container_width=True)

        elif sql_choice == "category":
            st.code("""
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
            """, language="sql")
            t0 = time.time()
            res_df = get_category_performance()
            st.success(f"Executed successfully in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(res_df, use_container_width=True)

        elif sql_choice == "custom":
            custom_query = st.text_area(
                "Enter SELECT SQL query:",
                value="SELECT country, COUNT(invoice_no) as orders, ROUND(SUM(total_amount), 2) as sales FROM orders GROUP BY country ORDER BY sales DESC LIMIT 10;",
                height=100
            )
            if st.button("▶️ Execute Custom SQL"):
                t0 = time.time()
                df_custom, err = execute_custom_sql(custom_query)
                if err:
                    st.error(f"SQL Error: {err}")
                else:
                    st.success(f"Query returned {len(df_custom)} rows in {(time.time()-t0)*1000:.1f} ms")
                    st.dataframe(df_custom, use_container_width=True)

    # ------------------ MONGODB TAB ------------------
    with tab_mongo:
        st.subheader("MongoDB Aggregation Pipelines")
        st.markdown("Faculty requirement: Implements aggregation stages: `$match`, `$group`, `$sort`, `$project`.")
        
        mongo_pipe_choice = st.selectbox(
            "Select Pipeline Pipeline to Run:",
            [
                "Pipeline 1: SDG Indicators Grouped by Category ($match → $group → $sort → $project)",
                "Pipeline 2: Freight Logistics Emissions by Region ($match → $group → $sort → $project)",
                "Pipeline 3: Sustainability Recommendations by SDG Goal ($match → $group → $sort → $project)",
                "Interactive Custom JSON Aggregation Pipeline"
            ]
        )
        
        if "Pipeline 1" in mongo_pipe_choice:
            st.code("""
db.sdg_indicators.aggregate([
    { "$match": { "status": "active" } },
    { "$group": {
        "_id": "$category",
        "total_revenue": { "$sum": "$revenue" },
        "avg_return_rate_pct": { "$avg": "$return_rate_pct" },
        "total_cancelled_units": { "$sum": "$cancelled_units" },
        "total_packaging_kg": { "$sum": "$est_packaging_kg" },
        "durable_share_pct": { "$avg": "$durable_share_pct" }
    }},
    { "$sort": { "total_packaging_kg": -1 } },
    { "$project": {
        "Category": "$_id",
        "Revenue ($)": "$total_revenue",
        "Avg Return Rate (%)": "$avg_return_rate_pct",
        "Cancelled Units (Waste)": "$total_cancelled_units",
        "Est Packaging Footprint (kg)": "$total_packaging_kg",
        "Durable Goods Ratio (%)": "$durable_share_pct",
        "_id": 0
    }}
])
            """, language="json")
            t0 = time.time()
            m_res = aggregate_sdg_by_category()
            st.success(f"Pipeline executed in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(pd.DataFrame(m_res), use_container_width=True)

        elif "Pipeline 2" in mongo_pipe_choice:
            st.code("""
db.logistics_footprint.aggregate([
    { "$match": { "zone": { "$in": ["UK Domestic", "Europe Regional", "International Air"] } } },
    { "$group": {
        "_id": "$zone",
        "destination_count": { "$sum": 1 },
        "total_orders": { "$sum": "$order_count" },
        "total_freight_co2_kg": { "$sum": "$total_co2_kg" },
        "avg_units_per_order": { "$avg": "$avg_units_per_order" }
    }},
    { "$sort": { "total_freight_co2_kg": -1 } },
    { "$project": {
        "Logistics Zone": "$_id",
        "Destinations": "$destination_count",
        "Total Orders": "$total_orders",
        "Total Freight CO2 (kg)": "$total_freight_co2_kg",
        "Batching Efficiency (Units/Order)": "$avg_units_per_order",
        "_id": 0
    }}
])
            """, language="json")
            t0 = time.time()
            m_res = aggregate_logistics_footprint()
            st.success(f"Pipeline executed in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(pd.DataFrame(m_res), use_container_width=True)

        elif "Pipeline 3" in mongo_pipe_choice:
            st.code("""
db.sdg_recommendations.aggregate([
    { "$match": { "priority": { "$in": ["High", "Medium"] } } },
    { "$group": {
        "_id": "$sdg_goal",
        "initiative_count": { "$sum": 1 },
        "avg_expected_reduction_pct": { "$avg": "$potential_reduction_pct" },
        "initiatives": { "$push": "$title" }
    }},
    { "$sort": { "initiative_count": -1 } },
    { "$project": {
        "SDG Goal": "$_id",
        "Initiatives Count": "$initiative_count",
        "Avg Expected Impact (%)": "$avg_expected_reduction_pct",
        "Key Actions": "$initiatives",
        "_id": 0
    }}
])
            """, language="json")
            t0 = time.time()
            m_res = aggregate_recommendations_by_sdg()
            st.success(f"Pipeline executed in {(time.time()-t0)*1000:.1f} ms")
            st.dataframe(pd.DataFrame(m_res), use_container_width=True)

        else:
            cust_col = st.selectbox("Select Target Collection:", ["sdg_indicators", "logistics_footprint", "sdg_recommendations"])
            default_pipe = json.dumps([
                {"$match": {"priority": "High"}},
                {"$project": {"title": 1, "target": 1, "potential_reduction_pct": 1, "_id": 0}}
            ], indent=2)
            custom_pipe_str = st.text_area("Pipeline JSON Array:", value=default_pipe, height=140)
            if st.button("▶️ Run MongoDB Pipeline"):
                t0 = time.time()
                res, err = execute_custom_mongo_pipeline(cust_col, custom_pipe_str)
                if err:
                    st.error(f"MongoDB Pipeline Error: {err}")
                else:
                    st.success(f"Executed in {(time.time()-t0)*1000:.1f} ms | Found {len(res)} documents")
                    st.json(res)

    # ------------------ DATA EXPLORER TAB ------------------
    with tab_data:
        st.subheader("Filtered Dataset Explorer")
        st.caption(f"Showing {len(filtered_df):,} records according to active global filters.")
        
        display_cols = [
            "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
            "UnitPrice", "CustomerID", "Country", "Sales", "Category", "IsCancelled", "LogisticsZone"
        ]
        
        # Search text
        search_query = st.text_input("🔍 Search within descriptions or invoice IDs:", "")
        df_display = filtered_df[display_cols]
        if search_query.strip():
            mask = (
                df_display["Description"].str.contains(search_query, case=False, na=False) |
                df_display["InvoiceNo"].astype(str).str.contains(search_query, case=False, na=False)
            )
            df_display = df_display[mask]
            
        st.dataframe(df_display.head(500), use_container_width=True, height=400)
        st.caption("Displaying top 500 rows for preview.")
        
        # Download button
        csv_data = df_display.head(5000).to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Filtered Data (CSV)",
            data=csv_data,
            file_name="sdg_ecommerce_filtered_data.csv",
            mime="text/csv"
        )

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748b; font-size: 0.8rem;'>"
    "DCDS Lab ESE Project · SDG in E-Commerce Analysis · Developed for Antigravity IDE & Streamlit"
    "</div>",
    unsafe_allow_html=True
)
