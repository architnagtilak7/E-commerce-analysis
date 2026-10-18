# 📊 Complete Database Queries Guide
## Simple, Beginner-Friendly & Viva-Ready Explanations for SQL & MongoDB

---

## 💡 Quick Translator: SQL vs MongoDB Terms

If you're new to databases, here is a 10-second comparison:

| Concept | SQL (Relational / SQLite) | MongoDB (NoSQL / Atlas) | Simple English Analogy |
| :--- | :--- | :--- | :--- |
| **Container** | **Database** | **Database** | A digital filing cabinet |
| **Storage Unit** | **Table** | **Collection** | A specific folder inside the cabinet |
| **Single Entry** | **Row / Record** | **Document (JSON)** | One sheet of paper / sticky note |
| **Data Point** | **Column / Attribute** | **Field / Key** | One blank on that sheet (e.g., name, price) |
| **Linking Data** | **JOIN** (using foreign keys) | **Embedded Doc** or **Pipeline** | Sticking two sheets together |
| **Processing** | `SELECT ... GROUP BY` | **Aggregation Pipeline** | An assembly line where data is transformed |

---

# 🟦 PART 1: Relational SQL Queries (SQLite)

In our project, SQL is used for **structured financial transactions**.  
We have 3 main tables:
1. `orders`: Contains invoice number, date, country, and whether it was cancelled.
2. `products`: Contains stock code, description, and category.
3. `order_items`: Records which items were bought in each order, how many, and at what price.

---

### SQL Query 1: Top 5 Best-Selling Products by Revenue
📍 **Where in code:** Function `get_top_5_products_by_revenue()` in [`sql_database.py`](file:///c:/Archit/DCDS%20Project/sql_database.py#L205-L228)

#### 🎯 Goal in Plain English:
> *"Out of thousands of products, find the top 5 that generated the most money, but ignore any orders that were cancelled or returned."*

#### 💻 The SQL Code:
```sql
SELECT 
    p.stock_code AS "Stock Code",
    p.description AS "Product Description",
    p.category AS "Category",
    SUM(oi.quantity) AS "Units Sold",
    ROUND(SUM(oi.total_price), 2) AS "Total Revenue ($)"
FROM order_items oi
JOIN products p ON oi.stock_code = p.stock_code
JOIN orders o ON oi.invoice_no = o.invoice_no
WHERE o.is_cancelled = 0 AND oi.quantity > 0
GROUP BY p.stock_code, p.description, p.category
ORDER BY "Total Revenue ($)" DESC
LIMIT 5;
```

#### 🔍 Beginner-Friendly Breakdown (Line by Line):
1. **`FROM order_items oi`**:  
   Start in the `order_items` table where every purchase line item is recorded.
2. **`JOIN products p ON oi.stock_code = p.stock_code`**:  
   Look up each product code in the `products` catalog to get its human-readable title and category.
3. **`JOIN orders o ON oi.invoice_no = o.invoice_no`**:  
   Connect to the `orders` table to check if the purchase was valid or cancelled.
4. **`WHERE o.is_cancelled = 0 AND oi.quantity > 0`**:  
   Filter out refunds, cancelled orders, or returns (`is_cancelled = 1`).
5. **`GROUP BY p.stock_code, p.description, p.category`**:  
   Combine all sales of the same item into one row.
6. **`SUM(oi.quantity)` & `SUM(oi.total_price)`**:  
   Add up all the quantities sold and total dollars earned for that item.
7. **`ORDER BY "Total Revenue ($)" DESC LIMIT 5`**:  
   Sort from the highest dollar amount to lowest, and take only the top 5.

---

### SQL Query 2: Monthly Revenue & Return Trajectory
📍 **Where in code:** Function `get_monthly_revenue_summary()` in [`sql_database.py`](file:///c:/Archit/DCDS%20Project/sql_database.py#L230-L251)

#### 🎯 Goal in Plain English:
> *"For each month of the year, calculate: How many orders came in? How much money was made? How much was lost to cancellations/returns? And what was the net profit?"*

#### 💻 The SQL Code:
```sql
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
```

#### 🔍 Beginner-Friendly Breakdown:
1. **`substr(o.invoice_date, 1, 7)`**:  
   Trims a timestamp like `"2011-05-15 14:30:00"` down to just the Year-Month: `"2011-05"`.
2. **`COUNT(DISTINCT o.invoice_no)`**:  
   Counts how many unique orders happened in that month (avoiding duplicate counting).
3. **`CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END`**:  
   Simple `IF` condition: If the order was successful, add the money to Gross Revenue; otherwise add 0.
4. **`CASE WHEN o.is_cancelled = 1 THEN ABS(oi.total_price) ...`**:  
   If the order was cancelled, add the refunded amount to the Refunds column.
5. **`GROUP BY substr(...)`**:  
   Groups transactions into 12 calendar months from earliest to latest.

---

### SQL Query 3: Multi-Table JOIN (Recent Order Details)
📍 **Where in code:** Function `get_joined_order_details()` in [`sql_database.py`](file:///c:/Archit/DCDS%20Project/sql_database.py#L253-L278)

#### 🎯 Goal in Plain English:
> *"Show me a full receipt view of the most recent orders by pulling customer location from Table 1, order items from Table 2, and product names from Table 3."*

#### 💻 The SQL Code:
```sql
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
```

#### 🔍 Beginner-Friendly Breakdown:
- **Why we need JOINs**: In good database design (3rd Normal Form), we don't repeat the product description in every order row. Instead, we use Primary Keys (`invoice_no`, `stock_code`) and Foreign Keys to glue the tables together at query time.
- **`JOIN order_items oi ON o.invoice_no = oi.invoice_no`**: Connects the header (who and when) with the line items (how many).
- **`JOIN products p ON oi.stock_code = p.stock_code`**: Connects the item code with the actual product catalog.
- **`LIMIT 15`**: Only fetches the 15 most recent orders for high speed.

---

### SQL Query 4: Subquery Identifying Products Exceeding Average Sales
📍 **Where in code:** Function `get_products_exceeding_average_sales()` in [`sql_database.py`](file:///c:/Archit/DCDS%20Project/sql_database.py#L280-L322)

#### 🎯 Goal in Plain English:
> *"Step 1: Calculate the average revenue of every single product in the entire store ($2,631.27). Step 2: Show only the high-performing products that made more money than that average."*

#### 💻 The SQL Code:
```sql
SELECT 
    p.stock_code AS "Stock Code",
    p.description AS "Description",
    p.category AS "Category",
    ROUND(SUM(oi.total_price), 2) AS "Product Revenue ($)"
FROM order_items oi
JOIN products p ON oi.stock_code = p.stock_code
JOIN orders o ON oi.invoice_no = o.invoice_no
WHERE o.is_cancelled = 0 AND oi.quantity > 0
GROUP BY p.stock_code, p.description, p.category
HAVING SUM(oi.total_price) > (
    /* --- INNER SUBQUERY (Runs First) --- */
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
LIMIT 10;
```

#### 🔍 Beginner-Friendly Breakdown:
1. **The Inner Query (Inside Parentheses `(...)`)**:  
   This calculates what the "average product" makes. It groups by `stock_code`, finds total sales for each product, and takes the `AVG()`.
2. **The Outer Query**:  
   Calculates the sales for each individual product.
3. **`HAVING SUM(oi.total_price) > (...)`**:  
   Unlike `WHERE` (which filters individual rows), `HAVING` filters aggregated groups. It only allows products whose revenue is higher than the catalog average!
4. **Why this impresses examiners**: It proves you know how to use nested subqueries and dynamic filtering rather than hardcoding numbers.

---

### SQL Query 5: Category Durability & Performance Share (SDG 12)
📍 **Where in code:** Function `get_category_performance()` in [`sql_database.py`](file:///c:/Archit/DCDS%20Project/sql_database.py#L324-L345)

#### 🎯 Goal in Plain English:
> *"For each product category (Home Decor, Kitchenware, Gifts, etc.), calculate total orders, total revenue, average price, and what percentage of items sold were durable/reusable versus disposable (SDG 12)."*

#### 💻 The SQL Code:
```sql
SELECT 
    p.category AS "Category",
    COUNT(DISTINCT o.invoice_no) AS "Orders Count",
    SUM(oi.quantity) AS "Total Units Sold",
    ROUND(SUM(oi.total_price), 2) AS "Total Revenue ($)",
    ROUND(AVG(oi.unit_price), 2) AS "Avg Unit Price ($)",
    ROUND(
        SUM(CASE WHEN p.is_durable = 1 THEN oi.quantity ELSE 0 END) * 100.0 / SUM(oi.quantity), 
        1
    ) AS "Durable Units Share (%)"
FROM order_items oi
JOIN products p ON oi.stock_code = p.stock_code
JOIN orders o ON oi.invoice_no = o.invoice_no
WHERE o.is_cancelled = 0 AND oi.quantity > 0
GROUP BY p.category
ORDER BY "Total Revenue ($)" DESC;
```

#### 🔍 Beginner-Friendly Breakdown:
1. **`GROUP BY p.category`**:  
   Rolls up all data by product department (e.g., Kitchenware, Gifts, Home Decor).
2. **`CASE WHEN p.is_durable = 1 THEN oi.quantity ELSE 0 END`**:  
   Counts how many units sold were made of long-lasting, recyclable materials (e.g. ceramic, metal, glass) rather than single-use plastics or paper.
3. **`* 100.0 / SUM(oi.quantity)`**:  
   Converts that count into an exact percentage ratio.
4. **SDG 12 Relevance**: Shows which department encourages sustainable consumer buying habits.

---

# 🍃 PART 2: NoSQL Document Queries (MongoDB Atlas Aggregation Pipelines)

In MongoDB, data is stored as JSON documents.  
Instead of writing `SELECT` and `JOIN`, we use an **Aggregation Pipeline**.  
Think of it like a **factory assembly line**:
- **Stage 1 (`$match`)**: Inspection gate — throw out unwanted items.
- **Stage 2 (`$group`)**: Sorting station — group remaining items into bins and calculate totals.
- **Stage 3 (`$sort`)**: Ranking station — arrange bins from largest to smallest.
- **Stage 4 (`$project`)**: Packaging station — give fields neat names and hide private IDs.

---

### MongoDB Pipeline 1: Group SDG Indicators by Category (SDG 12 Waste & Packaging)
📍 **Where in code:** Function `aggregate_sdg_by_category()` in [`mongodb_database.py`](file:///c:/Archit/DCDS%20Project/mongodb_database.py#L166-L199)

#### 🎯 Goal in Plain English:
> *"Take all category sustainability records, filter only active ones, calculate total packaging waste (kg) and return waste, and rank categories from most wasteful to least wasteful."*

#### 💻 The MongoDB Pipeline:
```javascript
db.sdg_indicators.aggregate([
    // Stage 1: Filter
    { "$match": { "status": "active" } },

    // Stage 2: Group & Calculate
    { "$group": {
        "_id": "$category",
        "total_revenue": { "$sum": "$revenue" },
        "avg_return_rate_pct": { "$avg": "$return_rate_pct" },
        "total_cancelled_units": { "$sum": "$cancelled_units" },
        "total_packaging_kg": { "$sum": "$est_packaging_kg" },
        "durable_share_pct": { "$avg": "$durable_share_pct" }
    }},

    // Stage 3: Rank
    { "$sort": { "total_packaging_kg": -1 } },

    // Stage 4: Clean Display
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
```

#### 🔍 Assembly Line Breakdown:
1. **`$match`**:  
   Only lets documents through if `"status": "active"`. Archived or test documents are discarded.
2. **`$group`**:  
   Puts documents into bins based on `category` (`_id: "$category"`). Inside each bin, it sums revenue, computes average return rate, and sums estimated packaging scrap (kg).
3. **`$sort`**:  
   `-1` means descending. The category generating the highest packaging waste appears right at the top.
4. **`$project`**:  
   Renames internal technical keys like `total_packaging_kg` to clean UI labels like `"Est Packaging Footprint (kg)"` and hides `_id: 0`.

---

### MongoDB Pipeline 2: Transport Carbon Emissions by Logistics Corridor (SDG 9)
📍 **Where in code:** Function `aggregate_logistics_footprint()` in [`mongodb_database.py`](file:///c:/Archit/DCDS%20Project/mongodb_database.py#L201-L232)

#### 🎯 Goal in Plain English:
> *"Group shipping destinations into 3 transport corridors: UK Domestic (local delivery vans), Europe Regional (freight trucks), and International Air (cargo planes). Calculate total CO₂ emissions (kg) and batching efficiency."*

#### 💻 The MongoDB Pipeline:
```javascript
db.logistics_footprint.aggregate([
    // Stage 1: Filter
    { "$match": { 
        "zone": { "$in": ["UK Domestic", "Europe Regional", "International Air"] } 
    }},

    // Stage 2: Group by corridor
    { "$group": {
        "_id": "$zone",
        "destination_count": { "$sum": 1 },
        "total_orders": { "$sum": "$order_count" },
        "total_freight_co2_kg": { "$sum": "$total_co2_kg" },
        "avg_units_per_order": { "$avg": "$avg_units_per_order" }
    }},

    // Stage 3: Sort by emissions
    { "$sort": { "total_freight_co2_kg": -1 } },

    // Stage 4: Format output
    { "$project": {
        "Logistics Zone": "$_id",
        "Destinations": "$destination_count",
        "Total Orders": "$total_orders",
        "Total Freight CO2 (kg)": "$total_freight_co2_kg",
        "Batching Efficiency (Units/Order)": "$avg_units_per_order",
        "_id": 0
    }}
])
```

#### 🔍 Assembly Line Breakdown:
1. **`$match`**:  
   Ensures only recognized logistics zones are processed.
2. **`$group`**:  
   Takes all international countries (France, Germany, Australia, etc.) and rolls them up by shipping mode.
3. **`$sort`**:  
   Orders from the most polluting transport corridor to the greenest.
4. **Key Finding**:  
   Reveals that while UK Domestic handles 90%+ of orders, its emissions per order are small (~0.45 kg CO₂). In contrast, International Air orders emit ~8.5 kg CO₂ per order, showing why consolidating orders into fewer packages is vital for SDG 9.

---

### MongoDB Pipeline 3: Actionable ESG Recommendations Grouped by SDG Goal
📍 **Where in code:** Function `aggregate_recommendations_by_sdg()` in [`mongodb_database.py`](file:///c:/Archit/DCDS%20Project/mongodb_database.py#L234-L263)

#### 🎯 Goal in Plain English:
> *"Filter only High and Medium priority sustainability recommendations, group them by UN SDG Target (SDG 12 vs SDG 9), calculate the average carbon/waste reduction potential, and bundle the action items into an array."*

#### 💻 The MongoDB Pipeline:
```javascript
db.sdg_recommendations.aggregate([
    // Stage 1: Filter priority
    { "$match": { "priority": { "$in": ["High", "Medium"] } } },

    // Stage 2: Group by SDG Goal & bundle actions
    { "$group": {
        "_id": "$sdg_goal",
        "initiative_count": { "$sum": 1 },
        "avg_expected_reduction_pct": { "$avg": "$potential_reduction_pct" },
        "initiatives": { "$push": "$title" }
    }},

    // Stage 3: Sort
    { "$sort": { "initiative_count": -1 } },

    // Stage 4: Project
    { "$project": {
        "SDG Goal": "$_id",
        "Initiatives Count": "$initiative_count",
        "Avg Expected Impact (%)": "$avg_expected_reduction_pct",
        "Key Actions": "$initiatives",
        "_id": 0
    }}
])
```

#### 🔍 Assembly Line Breakdown:
1. **`$match`**:  
   Ignores low-priority suggestions and keeps only urgent initiatives.
2. **`$push`**:  
   A unique MongoDB feature! Unlike SQL (which requires another table or complex string concatenation), MongoDB can take strings and assemble them into a native JSON array of actions (`["Eco-Packaging", "Return Reason Logging"]`).
3. **`$project`**:  
   Outputs a ready-to-display executive summary for management.

---

# 🎓 Quick Viva Questions & Answers

### Q1: Why did you use BOTH SQLite and MongoDB Atlas?
> **Answer:**  
> *"We used SQLite (Relational SQL) for order transactions because customer orders, line items, and financial records require strict tables, primary/foreign key relationships, and ACID compliance to prevent billing errors. We used MongoDB Atlas (NoSQL) for sustainability indicators and carbon models because environmental metrics, logistics footprint documents, and ESG recommendations have flexible, nested structures that benefit from document schemas and multi-stage aggregation pipelines."*

### Q2: What is the difference between SQL `JOIN` and MongoDB Aggregation?
> **Answer:**  
> *"In SQL, a `JOIN` connects multiple rigid relational tables on the fly using matching IDs. In MongoDB, data is usually stored as self-contained JSON documents, and an Aggregation Pipeline processes these documents through sequential stages (`$match`, `$group`, `$sort`, `$project`) like a data transformation pipeline."*

### Q3: What is the most complex SQL query in your project?
> **Answer:**  
> *"Query 4: The Subquery identifying products exceeding catalog average sales. It uses a nested subquery to first calculate the catalog-wide average revenue ($2,631.27), and then applies a `HAVING` clause to filter out products whose total revenue beats that average."*
