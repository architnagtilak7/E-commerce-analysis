/**
 * ECO-METRICS: Frontend Application Logic
 * Pure Vanilla JavaScript (ES6+) with Chart.js
 */

document.addEventListener("DOMContentLoaded", () => {
    // Active Global Filters
    const state = {
        country: "All",
        category: "All",
        status: "all",
        search: ""
    };

    // Chart.js Instances Registry
    const charts = {};

    // Presets for SQL & MongoDB
    const SQL_TEMPLATES = {
        top5: `SELECT \n    p.stock_code AS "Stock Code", \n    p.description AS "Description", \n    p.category AS "Category", \n    SUM(oi.quantity) AS "Units Sold", \n    ROUND(SUM(oi.total_price), 2) AS "Total Revenue ($)" \nFROM order_items oi \nJOIN products p ON oi.stock_code = p.stock_code \nJOIN orders o ON oi.invoice_no = o.invoice_no \nWHERE o.is_cancelled = 0 AND oi.quantity > 0 \nGROUP BY p.stock_code, p.description, p.category \nORDER BY "Total Revenue ($)" DESC \nLIMIT 5;`,
        monthly: `SELECT \n    substr(o.invoice_date, 1, 7) AS "Month", \n    COUNT(DISTINCT o.invoice_no) AS "Orders", \n    ROUND(SUM(CASE WHEN o.is_cancelled = 0 THEN oi.total_price ELSE 0 END), 2) AS "Gross Revenue ($)", \n    ROUND(SUM(CASE WHEN o.is_cancelled = 1 THEN ABS(oi.total_price) ELSE 0 END), 2) AS "Refunds ($)", \n    ROUND(SUM(oi.total_price), 2) AS "Net Revenue ($)" \nFROM orders o \nJOIN order_items oi ON o.invoice_no = oi.invoice_no \nGROUP BY substr(o.invoice_date, 1, 7) \nORDER BY "Month" ASC;`,
        join: `SELECT \n    o.invoice_no AS "Invoice No", \n    substr(o.invoice_date, 1, 10) AS "Date", \n    o.country AS "Country", \n    p.stock_code AS "Stock Code", \n    p.description AS "Description", \n    p.category AS "Category", \n    oi.quantity AS "Quantity", \n    oi.unit_price AS "Unit Price", \n    oi.total_price AS "Total ($)" \nFROM orders o \nJOIN order_items oi ON o.invoice_no = oi.invoice_no \nJOIN products p ON oi.stock_code = p.stock_code \nWHERE o.is_cancelled = 0 \nORDER BY o.invoice_date DESC \nLIMIT 15;`,
        subquery: `SELECT \n    p.stock_code AS "Stock Code", \n    p.description AS "Description", \n    p.category AS "Category", \n    SUM(oi.quantity) AS "Units", \n    ROUND(SUM(oi.total_price), 2) AS "Revenue ($)" \nFROM order_items oi \nJOIN products p ON oi.stock_code = p.stock_code \nJOIN orders o ON oi.invoice_no = o.invoice_no \nWHERE o.is_cancelled = 0 AND oi.quantity > 0 \nGROUP BY p.stock_code, p.description, p.category \nHAVING SUM(oi.total_price) > ( \n    SELECT AVG(sub_revenue) FROM ( \n        SELECT SUM(sub_oi.total_price) AS sub_revenue \n        FROM order_items sub_oi \n        JOIN orders sub_o ON sub_oi.invoice_no = sub_o.invoice_no \n        WHERE sub_o.is_cancelled = 0 AND sub_oi.quantity > 0 \n        GROUP BY sub_oi.stock_code \n    ) \n) \nORDER BY "Revenue ($)" DESC \nLIMIT 10;`,
        category: `SELECT \n    p.category AS "Category", \n    COUNT(DISTINCT o.invoice_no) AS "Orders", \n    SUM(oi.quantity) AS "Units Sold", \n    ROUND(SUM(oi.total_price), 2) AS "Revenue ($)", \n    ROUND(AVG(oi.unit_price), 2) AS "Avg Price ($)", \n    ROUND(SUM(CASE WHEN p.is_durable = 1 THEN oi.quantity ELSE 0 END) * 100.0 / SUM(oi.quantity), 1) AS "Durable %" \nFROM order_items oi \nJOIN products p ON oi.stock_code = p.stock_code \nJOIN orders o ON oi.invoice_no = o.invoice_no \nWHERE o.is_cancelled = 0 AND oi.quantity > 0 \nGROUP BY p.category \nORDER BY "Revenue ($)" DESC;`,
        custom: `SELECT country, COUNT(invoice_no) as orders, ROUND(SUM(total_amount), 2) as revenue FROM orders GROUP BY country ORDER BY revenue DESC LIMIT 10;`
    };

    const MONGO_TEMPLATES = {
        sdg_category: `[\n  { "$match": { "status": "active" } },\n  { "$group": {\n      "_id": "$category",\n      "total_revenue": { "$sum": "$revenue" },\n      "avg_return_rate_pct": { "$avg": "$return_rate_pct" },\n      "cancelled_units": { "$sum": "$cancelled_units" },\n      "est_packaging_kg": { "$sum": "$est_packaging_kg" }\n  }},\n  { "$sort": { "est_packaging_kg": -1 } },\n  { "$project": {\n      "Category": "$_id",\n      "Revenue ($)": "$total_revenue",\n      "Return Rate (%)": "$avg_return_rate_pct",\n      "Cancelled Units": "$cancelled_units",\n      "Packaging (kg)": "$est_packaging_kg",\n      "_id": 0\n  }}\n]`,
        logistics_zone: `[\n  { "$match": { "zone": { "$in": ["UK Domestic", "Europe Regional", "International Air"] } } },\n  { "$group": {\n      "_id": "$zone",\n      "destinations": { "$sum": 1 },\n      "total_orders": { "$sum": "$order_count" },\n      "total_freight_co2_kg": { "$sum": "$total_co2_kg" },\n      "avg_units_per_order": { "$avg": "$avg_units_per_order" }\n  }},\n  { "$sort": { "total_freight_co2_kg": -1 } },\n  { "$project": {\n      "Logistics Zone": "$_id",\n      "Destinations": "$destinations",\n      "Total Orders": "$total_orders",\n      "Freight CO2 (kg)": "$total_freight_co2_kg",\n      "Units / Order": "$avg_units_per_order",\n      "_id": 0\n  }}\n]`,
        recommendations: `[\n  { "$match": { "priority": { "$in": ["High", "Medium"] } } },\n  { "$group": {\n      "_id": "$sdg_goal",\n      "initiative_count": { "$sum": 1 },\n      "avg_impact_pct": { "$avg": "$potential_reduction_pct" },\n      "actions": { "$push": "$title" }\n  }},\n  { "$sort": { "initiative_count": -1 } },\n  { "$project": {\n      "SDG Goal": "$_id",\n      "Initiatives Count": "$initiative_count",\n      "Avg Impact (%)": "$avg_impact_pct",\n      "Actions": "$actions",\n      "_id": 0\n  }}\n]`,
        custom: `[\n  { "$match": { "priority": "High" } },\n  { "$project": { "title": 1, "target": 1, "potential_reduction_pct": 1, "_id": 0 } }\n]`
    };

    // ========================================================
    // HELPER: Chart Destruction & Re-creation
    // ========================================================
    function renderChart(canvasId, config) {
        if (charts[canvasId]) {
            charts[canvasId].destroy();
        }
        const ctx = document.getElementById(canvasId);
        if (ctx) {
            charts[canvasId] = new Chart(ctx, config);
        }
    }

    // Chart.js Global Theme Overrides
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.9)';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.1)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;

    // ========================================================
    // 1. HEALTH STATUS CHECK & DROPDOWNS
    // ========================================================
    async function checkHealth() {
        try {
            const res = await fetch("/api/health");
            const data = await res.json();
            
            const mongoPill = document.getElementById("db-mongo-status");
            const mongoLabel = mongoPill.querySelector(".status-label");
            
            if (data.mongodb.is_atlas && data.mongodb.mode === "live") {
                mongoPill.className = "status-pill status-live";
                mongoLabel.textContent = "MongoDB Atlas: LIVE";
            } else if (data.mongodb.mode === "live") {
                mongoPill.className = "status-pill status-live";
                mongoLabel.textContent = "MongoDB: Local Live";
            } else {
                mongoPill.className = "status-pill status-live";
                mongoLabel.textContent = "MongoDB: Embedded Engine";
            }
        } catch (e) {
            console.error("Health check error:", e);
        }
    }

    async function loadDropdowns() {
        try {
            const res = await fetch("/api/filters");
            const data = await res.json();
            
            const countrySelect = document.getElementById("filter-country");
            countrySelect.innerHTML = data.countries.map(c => `<option value="${c}">${c === 'All' ? 'All Countries (' + (data.countries.length - 1) + ')' : c}</option>`).join("");
            
            const catSelect = document.getElementById("filter-category");
            catSelect.innerHTML = data.categories.map(c => `<option value="${c}">${c === 'All' ? 'All Categories (' + (data.categories.length - 1) + ')' : c}</option>`).join("");
        } catch (e) {
            console.error("Filter load error:", e);
        }
    }

    // ========================================================
    // 2. DATA LOADERS (Overview, Orders, SDG, Explorer)
    // ========================================================
    async function loadOverview() {
        const queryParams = new URLSearchParams({
            country: state.country,
            category: state.category,
            status: state.status
        });

        // 1. KPIs
        try {
            const kpiRes = await fetch(`/api/kpis?${queryParams}`);
            const kpi = await kpiRes.json();
            
            document.getElementById("kpi-gross-rev").textContent = `$${Math.round(kpi.gross_revenue).toLocaleString()}`;
            document.getElementById("kpi-net-rev").textContent = `$${Math.round(kpi.net_revenue).toLocaleString()}`;
            document.getElementById("kpi-refund-meta").textContent = `After -$${Math.round(kpi.refund_amount).toLocaleString()} refunds`;
            document.getElementById("kpi-orders-count").textContent = kpi.total_orders.toLocaleString();
            document.getElementById("kpi-orders-meta").textContent = `${kpi.fulfilled_orders.toLocaleString()} fulfilled | ${kpi.cancelled_orders.toLocaleString()} ret`;
            document.getElementById("kpi-units-sold").textContent = kpi.total_units_sold.toLocaleString();
            document.getElementById("kpi-aov-meta").textContent = `Avg Order Value: $${kpi.avg_order_value.toFixed(2)}`;
            document.getElementById("kpi-customers").textContent = kpi.unique_customers.toLocaleString();
        } catch (e) { console.error("KPI Error:", e); }

        // 2. Monthly Trends Chart
        try {
            const monthlyRes = await fetch(`/api/monthly-trends?${queryParams}`);
            const monthly = await monthlyRes.json();
            
            renderChart("chart-monthly-trends", {
                type: 'bar',
                data: {
                    labels: monthly.map(m => m.YearMonth),
                    datasets: [
                        {
                            type: 'line',
                            label: 'Net Sales ($)',
                            data: monthly.map(m => m.net_revenue),
                            borderColor: '#10b981',
                            borderWidth: 3,
                            fill: false,
                            tension: 0.35,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Gross Sales ($)',
                            data: monthly.map(m => m.fulfilled_revenue),
                            backgroundColor: 'rgba(14, 165, 233, 0.75)',
                            borderRadius: 4,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Refunds ($)',
                            data: monthly.map(m => m.refund_amount),
                            backgroundColor: 'rgba(244, 63, 94, 0.75)',
                            borderRadius: 4,
                            yAxisID: 'y'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });
        } catch (e) { console.error("Monthly chart error:", e); }

        // 3. Top Products Chart
        try {
            const topRes = await fetch("/api/top-products?n=8&by=revenue");
            const topData = await topRes.json();
            
            renderChart("chart-top-products", {
                type: 'bar',
                data: {
                    labels: topData.map(p => p.Description.length > 20 ? p.Description.substring(0, 20) + '...' : p.Description),
                    datasets: [{
                        label: 'Gross Sales ($)',
                        data: topData.map(p => p.revenue),
                        backgroundColor: '#38bdf8',
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { display: false } }
                    }
                }
            });
        } catch (e) { console.error("Top products chart error:", e); }

        // 4. Category Share Donut
        try {
            const catRes = await fetch("/api/category-share");
            const catData = await catRes.json();
            
            renderChart("chart-category-share", {
                type: 'doughnut',
                data: {
                    labels: catData.map(c => c.Category),
                    datasets: [{
                        data: catData.map(c => c.revenue),
                        backgroundColor: [
                            '#0ea5e9', '#10b981', '#8b5cf6', '#f59e0b',
                            '#f43f5e', '#06b6d4', '#64748b'
                        ],
                        borderWidth: 2,
                        borderColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'right' } }
                }
            });
        } catch (e) { console.error("Category chart error:", e); }

        // 5. Country Breakdown
        try {
            const cancRes = await fetch("/api/cancellations");
            const cancData = await cancRes.json();
            const topCountries = cancData.country_cancellation_rates.slice(0, 8);
            
            renderChart("chart-countries", {
                type: 'bar',
                data: {
                    labels: topCountries.map(c => c.Country),
                    datasets: [{
                        label: 'Total Invoices Placed',
                        data: topCountries.map(c => c['Total Orders']),
                        backgroundColor: '#8b5cf6',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });
        } catch (e) { console.error("Country chart error:", e); }
    }

    async function loadOrders() {
        try {
            const cancRes = await fetch("/api/cancellations");
            const data = await cancRes.json();
            
            // Top Returned Bar
            const topRet = data.top_returned_products.slice(0, 8);
            renderChart("chart-top-returned", {
                type: 'bar',
                data: {
                    labels: topRet.map(p => p.Description.length > 22 ? p.Description.substring(0, 22) + '...' : p.Description),
                    datasets: [{
                        label: 'Units Returned (Scrap)',
                        data: topRet.map(p => p.returned_quantity),
                        backgroundColor: '#f43f5e',
                        borderRadius: 6
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { display: false } }
                    }
                }
            });

            // Country Cancellation Rate
            const cRates = data.country_cancellation_rates.slice(0, 10);
            renderChart("chart-country-canc", {
                type: 'bar',
                data: {
                    labels: cRates.map(c => c.Country),
                    datasets: [{
                        label: 'Cancellation Rate (%)',
                        data: cRates.map(c => c['Cancellation Rate (%)']),
                        backgroundColor: '#fbbf24',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });

            // Day Pattern
            renderChart("chart-day-patterns", {
                type: 'bar',
                data: {
                    labels: data.day_pattern.map(d => d.day),
                    datasets: [
                        {
                            label: 'Fulfilled Invoices',
                            data: data.day_pattern.map(d => d.fulfilled),
                            backgroundColor: '#0ea5e9',
                            borderRadius: 4
                        },
                        {
                            label: 'Cancelled Invoices',
                            data: data.day_pattern.map(d => d.cancelled),
                            backgroundColor: '#f43f5e',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });
        } catch (e) { console.error("Orders load error:", e); }
    }

    async function loadSdg() {
        // SDG 12
        try {
            const res12 = await fetch("/api/sdg12");
            const data12 = await res12.json();
            
            document.getElementById("sdg-ret-waste").textContent = data12.returned_units.toLocaleString();
            document.getElementById("sdg-pack-scrap").textContent = `${Math.round(data12.wasted_packaging_kg).toLocaleString()} kg`;
            document.getElementById("sdg-durable-pct").textContent = `${data12.durable_ratio_pct}%`;
            document.getElementById("sdg-pack-mass").textContent = `${Math.round(data12.fulfilled_packaging_kg).toLocaleString()} kg`;

            // Packaging by Category
            renderChart("chart-sdg12-packaging", {
                type: 'bar',
                data: {
                    labels: data12.category_metrics.map(c => c.Category),
                    datasets: [{
                        label: 'Packaging Footprint (kg)',
                        data: data12.category_metrics.map(c => c.packaging_kg),
                        backgroundColor: '#f59e0b',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });

            // Durability Share Donut
            renderChart("chart-sdg12-durability", {
                type: 'doughnut',
                data: {
                    labels: ['Durable Goods (Circular)', 'Single-Use / Ephemeral'],
                    datasets: [{
                        data: [data12.durable_ratio_pct, (100 - data12.durable_ratio_pct).toFixed(1)],
                        backgroundColor: ['#10b981', '#334155'],
                        borderWidth: 2,
                        borderColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });

            // Populate Recommendations
            const recGrid = document.getElementById("sdg12-recs-grid");
            recGrid.innerHTML = data12.recommendations.map(r => `
                <div class="rec-card">
                    <div class="rec-header">
                        <span class="rec-title">📌 ${r.title}</span>
                        <span class="badge badge-rose">${r.priority} Priority</span>
                    </div>
                    <p class="rec-desc">${r.description}</p>
                    <div class="rec-footer">
                        <span class="rec-target">${r.target} · ${r.timeline}</span>
                        <span class="rec-impact">🎯 -${r.potential_reduction_pct}% ${r.metric}</span>
                    </div>
                </div>
            `).join("");
        } catch (e) { console.error("SDG 12 error:", e); }

        // SDG 9
        try {
            const res9 = await fetch("/api/sdg9");
            const data9 = await res9.json();

            document.getElementById("sdg9-total-co2").textContent = `${Math.round(data9.total_co2_kg).toLocaleString()} kg`;
            const ukRow = data9.zone_summary.find(z => z.LogisticsZone === "UK Domestic");
            const ukCo2 = ukRow ? ukRow.total_co2_kg : 0;
            document.getElementById("sdg9-uk-co2").textContent = `${Math.round(ukCo2).toLocaleString()} kg`;
            document.getElementById("sdg9-intl-co2").textContent = `${Math.round(data9.total_co2_kg - ukCo2).toLocaleString()} kg`;

            // Zones Chart
            renderChart("chart-sdg9-zones", {
                type: 'bar',
                data: {
                    labels: data9.zone_summary.map(z => z.LogisticsZone),
                    datasets: [{
                        label: 'Transport CO2e (kg)',
                        data: data9.zone_summary.map(z => z.total_co2_kg),
                        backgroundColor: ['#0ea5e9', '#8b5cf6', '#f43f5e'],
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });

            // Batching Chart
            renderChart("chart-sdg9-batching", {
                type: 'bar',
                data: {
                    labels: data9.zone_summary.map(z => z.LogisticsZone),
                    datasets: [{
                        label: 'Avg Units per Order Shipment',
                        data: data9.zone_summary.map(z => z.avg_units_per_order),
                        backgroundColor: '#06b6d4',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                }
            });

            // Populate SDG 9 Recommendations
            const rec9Grid = document.getElementById("sdg9-recs-grid");
            rec9Grid.innerHTML = data9.recommendations.map(r => `
                <div class="rec-card">
                    <div class="rec-header">
                        <span class="rec-title">🚛 ${r.title}</span>
                        <span class="badge badge-accent">${r.priority} Priority</span>
                    </div>
                    <p class="rec-desc">${r.description}</p>
                    <div class="rec-footer">
                        <span class="rec-target">${r.target} · ${r.timeline}</span>
                        <span class="rec-impact">🎯 -${r.potential_reduction_pct}% ${r.metric}</span>
                    </div>
                </div>
            `).join("");
        } catch (e) { console.error("SDG 9 error:", e); }
    }

    async function loadRawData() {
        const queryParams = new URLSearchParams({
            q: state.search,
            country: state.country,
            category: state.category,
            status: state.status,
            limit: 50
        });
        
        try {
            const res = await fetch(`/api/data?${queryParams}`);
            const data = await res.json();
            
            const container = document.getElementById("raw-data-table-container");
            if (data.records.length === 0) {
                container.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted);">No records match the current search & filters.</div>`;
                return;
            }

            const headers = Object.keys(data.records[0]);
            let html = `<table class="data-table"><thead><tr>`;
            headers.forEach(h => html += `<th>${h}</th>`);
            html += `</tr></thead><tbody>`;
            
            data.records.forEach(row => {
                html += `<tr>`;
                headers.forEach(h => {
                    let val = row[h];
                    if (h === 'IsCancelled') {
                        val = val ? '<span class="badge badge-rose">Cancelled</span>' : '<span class="badge badge-emerald">Fulfilled</span>';
                    }
                    html += `<td>${val}</td>`;
                });
                html += `</tr>`;
            });
            html += `</tbody></table>`;
            container.innerHTML = html;
        } catch (e) { console.error("Raw data error:", e); }
    }

    // ========================================================
    // 3. QUERY RUNNER HANDLERS (SQL & MONGODB)
    // ========================================================
    const sqlPreset = document.getElementById("sql-preset-select");
    const sqlEditor = document.getElementById("sql-editor");
    const btnRunSql = document.getElementById("btn-run-sql");
    const sqlTable = document.getElementById("sql-table-container");
    const sqlTiming = document.getElementById("sql-timing");

    sqlEditor.value = SQL_TEMPLATES.top5;

    sqlPreset.addEventListener("change", () => {
        const key = sqlPreset.value;
        sqlEditor.value = SQL_TEMPLATES[key] || "";
    });

    btnRunSql.addEventListener("click", async () => {
        btnRunSql.disabled = true;
        btnRunSql.textContent = "Executing...";
        sqlTiming.textContent = "";
        
        try {
            const key = sqlPreset.value;
            const res = await fetch("/api/sql", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query_key: key,
                    custom_sql: key === "custom" ? sqlEditor.value : null
                })
            });
            const result = await res.json();
            
            if (!res.ok) {
                sqlTable.innerHTML = `<div style="padding: 20px; color: #fb7185;">⚠️ ${result.detail}</div>`;
            } else {
                sqlTiming.textContent = `⚡ ${result.row_count} rows in ${result.execution_time_ms} ms`;
                let html = `<table class="data-table"><thead><tr>`;
                result.columns.forEach(col => html += `<th>${col}</th>`);
                html += `</tr></thead><tbody>`;
                result.data.forEach(row => {
                    html += `<tr>`;
                    result.columns.forEach(col => html += `<td>${row[col] !== null ? row[col] : 'NULL'}</td>`);
                    html += `</tr>`;
                });
                html += `</tbody></table>`;
                sqlTable.innerHTML = html;
            }
        } catch (e) {
            sqlTable.innerHTML = `<div style="padding: 20px; color: #fb7185;">Error: ${e.message}</div>`;
        } finally {
            btnRunSql.disabled = false;
            btnRunSql.textContent = "▶️ Execute SQL Query";
        }
    });

    // Auto-run first SQL query
    btnRunSql.click();

    // MongoDB Pipeline Runner
    const mongoPreset = document.getElementById("mongo-preset-select");
    const mongoEditor = document.getElementById("mongo-editor");
    const btnRunMongo = document.getElementById("btn-run-mongo");
    const mongoTable = document.getElementById("mongo-table-container");
    const mongoTiming = document.getElementById("mongo-timing");

    mongoEditor.value = MONGO_TEMPLATES.sdg_category;

    mongoPreset.addEventListener("change", () => {
        const key = mongoPreset.value;
        mongoEditor.value = MONGO_TEMPLATES[key] || "";
    });

    btnRunMongo.addEventListener("click", async () => {
        btnRunMongo.disabled = true;
        btnRunMongo.textContent = "Running Pipeline...";
        mongoTiming.textContent = "";

        try {
            const key = mongoPreset.value;
            const res = await fetch("/api/mongo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    pipeline_key: key,
                    custom_collection: "sdg_indicators",
                    custom_pipeline_json: key === "custom" ? mongoEditor.value : null
                })
            });
            const result = await res.json();

            if (!res.ok) {
                mongoTable.innerHTML = `<div style="padding: 20px; color: #fb7185;">⚠️ ${result.detail}</div>`;
            } else {
                mongoTiming.textContent = `🍃 ${result.document_count} documents in ${result.execution_time_ms} ms`;
                if (result.documents.length === 0) {
                    mongoTable.innerHTML = `<div style="padding: 20px; color: var(--text-muted);">No documents matched the pipeline stages.</div>`;
                    return;
                }
                const headers = Object.keys(result.documents[0]);
                let html = `<table class="data-table"><thead><tr>`;
                headers.forEach(h => html += `<th>${h}</th>`);
                html += `</tr></thead><tbody>`;
                result.documents.forEach(doc => {
                    html += `<tr>`;
                    headers.forEach(h => {
                        let val = doc[h];
                        if (Array.isArray(val)) val = val.join(", ");
                        html += `<td>${val}</td>`;
                    });
                    html += `</tr>`;
                });
                html += `</tbody></table>`;
                mongoTable.innerHTML = html;
            }
        } catch (e) {
            mongoTable.innerHTML = `<div style="padding: 20px; color: #fb7185;">Error: ${e.message}</div>`;
        } finally {
            btnRunMongo.disabled = false;
            btnRunMongo.textContent = "▶️ Run MongoDB Pipeline";
        }
    });

    // Auto-run first Mongo query
    btnRunMongo.click();

    // Sync Atlas Button
    const btnSync = document.getElementById("btn-sync-atlas");
    btnSync.addEventListener("click", async () => {
        btnSync.disabled = true;
        btnSync.innerHTML = `<span class="sync-icon">⏳</span> Syncing...`;
        try {
            const res = await fetch("/api/sync-mongo", { method: "POST" });
            const data = await res.json();
            alert(`🎉 ${data.message}\nSeeded:\n- Indicators: ${data.seeded.sdg_indicators}\n- Logistics: ${data.seeded.logistics_footprint}\n- Recommendations: ${data.seeded.sdg_recommendations}\nExecution: ${data.execution_time_ms}ms`);
            checkHealth();
            btnRunMongo.click();
        } catch (e) {
            alert("Error syncing to MongoDB: " + e.message);
        } finally {
            btnSync.disabled = false;
            btnSync.innerHTML = `<span class="sync-icon">⚡</span> Sync Atlas`;
        }
    });

    // ========================================================
    // 4. TAB & FILTER EVENT LISTENERS
    // ========================================================
    // Main Nav Tabs
    document.querySelectorAll(".nav-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
            
            tab.classList.add("active");
            const target = document.getElementById(tab.dataset.tab);
            if (target) target.classList.add("active");

            // Refresh specific tab
            if (tab.dataset.tab === "tab-orders") loadOrders();
            if (tab.dataset.tab === "tab-sdg") loadSdg();
            if (tab.dataset.tab === "tab-queries") loadRawData();
        });
    });

    // SDG Subtabs
    document.querySelectorAll(".sdg-subtab").forEach(sub => {
        sub.addEventListener("click", () => {
            document.querySelectorAll(".sdg-subtab").forEach(s => s.classList.remove("active"));
            document.querySelectorAll(".sdg-subpanel").forEach(p => p.classList.remove("active"));
            
            sub.classList.add("active");
            const target = document.getElementById(sub.dataset.sdg + "-content");
            if (target) target.classList.add("active");
        });
    });

    // Query Engine Tabs
    document.querySelectorAll(".engine-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll(".engine-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".engine-panel").forEach(p => p.classList.remove("active"));
            
            tab.classList.add("active");
            const target = document.getElementById(tab.dataset.engine);
            if (target) target.classList.add("active");
            if (tab.dataset.engine === "engine-data") loadRawData();
        });
    });

    // Filter Change Handlers
    document.getElementById("filter-country").addEventListener("change", (e) => {
        state.country = e.target.value;
        loadOverview();
    });

    document.getElementById("filter-category").addEventListener("change", (e) => {
        state.category = e.target.value;
        loadOverview();
    });

    document.querySelectorAll("#order-status-toggles .toggle-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#order-status-toggles .toggle-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.status = btn.dataset.status;
            loadOverview();
        });
    });

    document.getElementById("btn-reset-filters").addEventListener("click", () => {
        state.country = "All";
        state.category = "All";
        state.status = "all";
        document.getElementById("filter-country").value = "All";
        document.getElementById("filter-category").value = "All";
        document.querySelectorAll("#order-status-toggles .toggle-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.status === "all");
        });
        loadOverview();
    });

    // Search Input in Explorer
    let searchTimeout;
    const searchInput = document.getElementById("data-search-input");
    searchInput.addEventListener("input", (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.search = e.target.value;
            loadRawData();
        }, 300);
    });

    // Export CSV
    document.getElementById("btn-export-csv").addEventListener("click", () => {
        const queryParams = new URLSearchParams({
            q: state.search,
            country: state.country,
            category: state.category,
            status: state.status,
            limit: 500
        });
        window.open(`/api/data?${queryParams}&format=csv`, '_blank');
    });

    // Initialize
    checkHealth();
    loadDropdowns();
    loadOverview();
});
