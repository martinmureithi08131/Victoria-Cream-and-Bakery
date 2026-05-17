import streamlit as st
import pandas as pd
import sqlite3
import io
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime

# ─────────────────────────────────────────────
# 1. PAGE CONFIGURATION
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Victoria Cream & Bakery",
    page_icon="🎂",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 2. CUSTOM STYLING
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Lato:wght@300;400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Lato', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Playfair Display', serif;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 15px;
        font-weight: 700;
        padding: 10px 20px;
    }
    .metric-card {
        background: linear-gradient(135deg, #fff7f0, #ffe8d6);
        border-left: 5px solid #d4622a;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }
    .metric-card h4 { margin: 0; font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card p  { margin: 4px 0 0; font-size: 26px; font-weight: 700; color: #2c2c2c; }
    .alert-row {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        border-radius: 6px;
        padding: 8px 14px;
        margin-bottom: 6px;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. DATABASE SETUP (SQLite — persistent)
# ─────────────────────────────────────────────
DB_PATH = "victoria_bakery.db"

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

conn = get_connection()

def init_db():
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            customer TEXT,
            details TEXT,
            amount REAL
        );
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            item TEXT,
            quantity REAL,
            unit TEXT,
            cost REAL
        );
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            person TEXT,
            type TEXT,
            amount REAL,
            status TEXT
        );
    """)
    conn.commit()

init_db()

# ─────────────────────────────────────────────
# 4. DATA HELPERS
# ─────────────────────────────────────────────
def load_sales():
    return pd.read_sql("SELECT * FROM sales ORDER BY date DESC", conn)

def load_ingredients():
    return pd.read_sql("SELECT * FROM ingredients ORDER BY date DESC", conn)

def load_debts():
    return pd.read_sql("SELECT * FROM debts ORDER BY date DESC", conn)

def insert_sale(date_val, customer, details, amount):
    conn.execute("INSERT INTO sales (date, customer, details, amount) VALUES (?,?,?,?)",
                 (date_val, customer, details, amount))
    conn.commit()

def insert_ingredient(date_val, item, quantity, unit, cost):
    conn.execute("INSERT INTO ingredients (date, item, quantity, unit, cost) VALUES (?,?,?,?,?)",
                 (date_val, item, quantity, unit, cost))
    conn.commit()

def insert_debt(date_val, person, dtype, amount, status):
    conn.execute("INSERT INTO debts (date, person, type, amount, status) VALUES (?,?,?,?,?)",
                 (date_val, person, dtype, amount, status))
    conn.commit()

def delete_row(table, row_id):
    conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
    conn.commit()

def update_debt_status(row_id, new_status):
    conn.execute("UPDATE debts SET status=? WHERE id=?", (new_status, row_id))
    conn.commit()

# ─────────────────────────────────────────────
# 5. EXCEL EXPORT
# ─────────────────────────────────────────────
def export_excel():
    sales_df       = load_sales()
    ingredients_df = load_ingredients()
    debts_df       = load_debts()

    # Auto-compute cashflow by month
    sales_df["month"] = pd.to_datetime(sales_df["date"]).dt.to_period("M").astype(str)
    ingr_df2 = ingredients_df.copy()
    ingr_df2["month"] = pd.to_datetime(ingr_df2["date"]).dt.to_period("M").astype(str)

    income_by_month   = sales_df.groupby("month")["amount"].sum().reset_index().rename(columns={"amount": "Total Income (Ksh)"})
    expense_by_month  = ingr_df2.groupby("month")["cost"].sum().reset_index().rename(columns={"cost": "Total Expenses (Ksh)"})
    cashflow = income_by_month.merge(expense_by_month, on="month", how="outer").fillna(0)
    cashflow["Net Profit (Ksh)"] = cashflow["Total Income (Ksh)"] - cashflow["Total Expenses (Ksh)"]
    cashflow.rename(columns={"month": "Month"}, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        cashflow.to_excel(writer, index=False, sheet_name="Cashflow Summary")
        ingredients_df.to_excel(writer, index=False, sheet_name="Ingredients")
        sales_df.to_excel(writer, index=False, sheet_name="Sales and Orders")
        debts_df.to_excel(writer, index=False, sheet_name="Debts & Credit")
    return output.getvalue()

# ─────────────────────────────────────────────
# 6. SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎂 Victoria Cream & Bakery")
    st.markdown("---")

    # KPI snapshot
    sales_df_s = load_sales()
    ingr_df_s  = load_ingredients()
    debts_df_s = load_debts()

    total_income   = sales_df_s["amount"].sum() if not sales_df_s.empty else 0
    total_expenses = ingr_df_s["cost"].sum()    if not ingr_df_s.empty else 0
    net_profit     = total_income - total_expenses
    pending_debts  = debts_df_s[debts_df_s["status"] != "Cleared"]["amount"].sum() if not debts_df_s.empty else 0

    st.markdown(f"""
    <div class="metric-card"><h4>Total Revenue</h4><p>Ksh {total_income:,.0f}</p></div>
    <div class="metric-card"><h4>Total Expenses</h4><p>Ksh {total_expenses:,.0f}</p></div>
    <div class="metric-card"><h4>Net Profit</h4><p>Ksh {net_profit:,.0f}</p></div>
    <div class="metric-card"><h4>Pending Debts</h4><p>Ksh {pending_debts:,.0f}</p></div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📥 Export Data")
    st.download_button(
        label="⬇️ Download Excel Report",
        data=export_excel(),
        file_name=f"Victoria-Bakery-{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )

# ─────────────────────────────────────────────
# 7. MAIN CONTENT
# ─────────────────────────────────────────────
st.title("🎂 Victoria Cream & Bakery — Business System")

tab1, tab2, tab3, tab4 = st.tabs(["🎂 Sales & Orders", "🛒 Ingredients", "💳 Debts & Credit", "📈 Cashflow"])

# ══════════════════════════════════════════════
# TAB 1 — SALES & ORDERS
# ══════════════════════════════════════════════
with tab1:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("New Order Entry")
        with st.form("sales_form", clear_on_submit=True):
            sale_date  = st.date_input("Date", value=date.today())
            customer   = st.text_input("Customer Name")
            details    = st.text_area("Cake / Order Details")
            amount     = st.number_input("Amount (Ksh)", min_value=0.0, step=100.0)
            if st.form_submit_button("💾 Save Order", use_container_width=True):
                if customer and amount > 0:
                    insert_sale(str(sale_date), customer, details, amount)
                    st.success(f"Order for {customer} saved!")
                    st.rerun()
                else:
                    st.warning("Please fill in Customer Name and Amount.")

    with col2:
        st.subheader("All Orders")
        sales_df = load_sales()

        # Date filter
        if not sales_df.empty:
            f1, f2 = st.columns(2)
            min_d = pd.to_datetime(sales_df["date"]).min().date()
            max_d = pd.to_datetime(sales_df["date"]).max().date()
            start = f1.date_input("From", value=min_d, key="s_start")
            end   = f2.date_input("To",   value=max_d, key="s_end")
            mask  = (pd.to_datetime(sales_df["date"]).dt.date >= start) & \
                    (pd.to_datetime(sales_df["date"]).dt.date <= end)
            filtered = sales_df[mask]
        else:
            filtered = sales_df

        st.dataframe(
            filtered[["id","date","customer","details","amount"]].rename(columns={
                "id":"ID","date":"Date","customer":"Customer",
                "details":"Order Details","amount":"Amount (Ksh)"
            }),
            use_container_width=True, hide_index=True
        )

        # Delete a row
        if not filtered.empty:
            del_id = st.number_input("Delete Order by ID", min_value=1, step=1, key="del_sale")
            if st.button("🗑️ Delete Order", key="btn_del_sale"):
                delete_row("sales", del_id)
                st.success("Order deleted.")
                st.rerun()

# ══════════════════════════════════════════════
# TAB 2 — INGREDIENTS
# ══════════════════════════════════════════════
with tab2:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Log Ingredient Cost")
        with st.form("ingredient_form", clear_on_submit=True):
            ingr_date = st.date_input("Date", value=date.today(), key="ingr_date")
            item      = st.text_input("Item Name")
            qty       = st.number_input("Quantity", min_value=0.0, step=0.5)
            unit      = st.selectbox("Unit", ["kg", "g", "litres", "ml", "pieces", "packets", "other"])
            cost      = st.number_input("Cost (Ksh)", min_value=0.0, step=50.0)
            if st.form_submit_button("💾 Save Ingredient", use_container_width=True):
                if item and cost > 0:
                    insert_ingredient(str(ingr_date), item, qty, unit, cost)
                    st.success(f"{item} logged!")
                    st.rerun()
                else:
                    st.warning("Please fill in Item Name and Cost.")

    with col2:
        st.subheader("Ingredient Expenses")
        ingr_df = load_ingredients()

        if not ingr_df.empty:
            f1, f2 = st.columns(2)
            min_d = pd.to_datetime(ingr_df["date"]).min().date()
            max_d = pd.to_datetime(ingr_df["date"]).max().date()
            start = f1.date_input("From", value=min_d, key="i_start")
            end   = f2.date_input("To",   value=max_d, key="i_end")
            mask  = (pd.to_datetime(ingr_df["date"]).dt.date >= start) & \
                    (pd.to_datetime(ingr_df["date"]).dt.date <= end)
            filtered_i = ingr_df[mask]
        else:
            filtered_i = ingr_df

        st.dataframe(
            filtered_i[["id","date","item","quantity","unit","cost"]].rename(columns={
                "id":"ID","date":"Date","item":"Item","quantity":"Qty",
                "unit":"Unit","cost":"Cost (Ksh)"
            }),
            use_container_width=True, hide_index=True
        )

        # Low stock / high cost alerts
        if not ingr_df.empty:
            avg_cost = ingr_df.groupby("item")["cost"].mean()
            top3 = avg_cost.nlargest(3)
            if not top3.empty:
                st.markdown("**⚠️ Top 3 Costliest Ingredients (average)**")
                for itm, cst in top3.items():
                    st.markdown(f'<div class="alert-row">🔴 <b>{itm}</b> — avg Ksh {cst:,.0f}</div>', unsafe_allow_html=True)

        if not filtered_i.empty:
            del_id = st.number_input("Delete Ingredient by ID", min_value=1, step=1, key="del_ingr")
            if st.button("🗑️ Delete Ingredient", key="btn_del_ingr"):
                delete_row("ingredients", del_id)
                st.success("Ingredient deleted.")
                st.rerun()

# ══════════════════════════════════════════════
# TAB 3 — DEBTS & CREDIT
# ══════════════════════════════════════════════
with tab3:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Record Debt / Credit")
        with st.form("debt_form", clear_on_submit=True):
            debt_date = st.date_input("Date", value=date.today(), key="debt_date")
            person    = st.text_input("Person / Entity")
            dtype     = st.selectbox("Type", ["Owed to us (Debtor)", "We owe them (Creditor)"])
            amount    = st.number_input("Amount (Ksh)", min_value=0.0, step=100.0)
            status    = st.selectbox("Status", ["Unpaid", "Partially Paid", "Cleared"])
            if st.form_submit_button("💾 Save Record", use_container_width=True):
                if person and amount > 0:
                    insert_debt(str(debt_date), person, dtype, amount, status)
                    st.success(f"Record for {person} saved!")
                    st.rerun()
                else:
                    st.warning("Please fill in Person/Entity and Amount.")

    with col2:
        st.subheader("Debts & Credit Records")
        debts_df = load_debts()

        st.dataframe(
            debts_df[["id","date","person","type","amount","status"]].rename(columns={
                "id":"ID","date":"Date","person":"Person/Entity",
                "type":"Type","amount":"Amount (Ksh)","status":"Status"
            }) if not debts_df.empty else debts_df,
            use_container_width=True, hide_index=True
        )

        if not debts_df.empty:
            st.markdown("---")
            uc1, uc2, uc3 = st.columns(3)
            upd_id  = uc1.number_input("Update Status by ID", min_value=1, step=1)
            new_st  = uc2.selectbox("New Status", ["Unpaid", "Partially Paid", "Cleared"])
            if uc3.button("✅ Update", use_container_width=True):
                update_debt_status(upd_id, new_st)
                st.success("Status updated.")
                st.rerun()

            del_id = st.number_input("Delete Record by ID", min_value=1, step=1, key="del_debt")
            if st.button("🗑️ Delete Record", key="btn_del_debt"):
                delete_row("debts", del_id)
                st.success("Record deleted.")
                st.rerun()

# ══════════════════════════════════════════════
# TAB 4 — CASHFLOW (AUTO-CALCULATED)
# ══════════════════════════════════════════════
with tab4:
    st.subheader("📈 Monthly Cashflow — Auto-Calculated from Sales & Ingredients")

    sales_df = load_sales()
    ingr_df  = load_ingredients()

    if sales_df.empty and ingr_df.empty:
        st.info("No data yet. Add sales and ingredient records to see cashflow.")
    else:
        # Build monthly summaries
        if not sales_df.empty:
            sales_df["month"] = pd.to_datetime(sales_df["date"]).dt.to_period("M").astype(str)
            income_m = sales_df.groupby("month")["amount"].sum().reset_index()
            income_m.columns = ["Month", "Income (Ksh)"]
        else:
            income_m = pd.DataFrame(columns=["Month", "Income (Ksh)"])

        if not ingr_df.empty:
            ingr_df["month"] = pd.to_datetime(ingr_df["date"]).dt.to_period("M").astype(str)
            expense_m = ingr_df.groupby("month")["cost"].sum().reset_index()
            expense_m.columns = ["Month", "Expenses (Ksh)"]
        else:
            expense_m = pd.DataFrame(columns=["Month", "Expenses (Ksh)"])

        cashflow = income_m.merge(expense_m, on="Month", how="outer").fillna(0).sort_values("Month")
        cashflow["Net Profit (Ksh)"] = cashflow["Income (Ksh)"] - cashflow["Expenses (Ksh)"]
        cashflow["Margin (%)"] = (
            cashflow["Net Profit (Ksh)"] / cashflow["Income (Ksh)"].replace(0, pd.NA) * 100
        ).round(1)

        # Summary table
        st.dataframe(cashflow, use_container_width=True, hide_index=True)

        # Charts
        if len(cashflow) > 0:
            c1, c2 = st.columns(2)

            with c1:
                fig1 = go.Figure()
                fig1.add_bar(x=cashflow["Month"], y=cashflow["Income (Ksh)"],
                             name="Income", marker_color="#2ecc71")
                fig1.add_bar(x=cashflow["Month"], y=cashflow["Expenses (Ksh)"],
                             name="Expenses", marker_color="#e74c3c")
                fig1.update_layout(
                    title="Income vs Expenses by Month",
                    barmode="group",
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_family="Lato"
                )
                st.plotly_chart(fig1, use_container_width=True)

            with c2:
                fig2 = px.line(
                    cashflow, x="Month", y="Net Profit (Ksh)",
                    title="Net Profit Trend",
                    markers=True,
                    color_discrete_sequence=["#d4622a"]
                )
                fig2.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_family="Lato"
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Pie — expense breakdown by ingredient
            if not ingr_df.empty:
                st.subheader("Expense Breakdown by Ingredient")
                breakdown = ingr_df.groupby("item")["cost"].sum().reset_index()
                fig3 = px.pie(breakdown, names="item", values="cost",
                              color_discrete_sequence=px.colors.qualitative.Pastel)
                fig3.update_layout(font_family="Lato")
                st.plotly_chart(fig3, use_container_width=True)
