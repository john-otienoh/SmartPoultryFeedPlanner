# app.py
"""
Smart Poultry Feed Planner - Offline MVP
Features:
- Feed Calculator
- Local Ingredient Matcher
- Nutritional Tracker
- Growth Stage Scheduler
- Cost Optimizer
- Data Logging (SQLite)
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import datetime as dt
from pathlib import Path

# Optional dependencies
try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False

try:
    from scipy.optimize import linprog
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False

# -----------------------
# Persistence (SQLite)
# -----------------------
DB_PATH = Path("smart_poultry.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # ingredients table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            protein REAL,
            energy REAL,
            calcium REAL,
            phosphorus REAL,
            fiber REAL,
            category TEXT,
            price REAL,
            availability TEXT
        )
    """)
    # batches (nutritional tracker)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY,
            name TEXT,
            date TEXT,
            recipe TEXT, -- json
            qty_kg REAL,
            total_protein REAL,
            total_calcium REAL,
            total_energy REAL,
            total_vitamins REAL,
            notes TEXT
        )
    """)
    # weights & mortality logging
    cur.execute("""
        CREATE TABLE IF NOT EXISTS flock_logs (
            id INTEGER PRIMARY KEY,
            flock_name TEXT,
            date TEXT,
            avg_weight_g REAL,
            mortality INTEGER,
            notes TEXT
        )
    """)
    conn.commit()
    return conn

# -----------------------
# Default ingredients (editable)
# -----------------------
DEFAULT_INGREDIENTS = [
    {"name": "Maize", "protein": 8.5, "energy": 3400, "calcium": 0.02, "phosphorus": 0.25, "fiber": 2.0, "category": "energy", "price": 15.0, "availability": "High"},
    {"name": "Sorghum", "protein": 9.0, "energy": 3300, "calcium": 0.03, "phosphorus": 0.28, "fiber": 2.5, "category": "energy", "price": 18.0, "availability": "Medium"},
    {"name": "Wheat Bran", "protein": 15.0, "energy": 1500, "calcium": 0.10, "phosphorus": 1.15, "fiber": 10.0, "category": "fiber", "price": 10.0, "availability": "High"},
    {"name": "Soybean Meal", "protein": 44.0, "energy": 2400, "calcium": 0.25, "phosphorus": 0.65, "fiber": 6.0, "category": "protein", "price": 40.0, "availability": "Medium"},
    {"name": "Fish Meal", "protein": 65.0, "energy": 3000, "calcium": 5.00, "phosphorus": 2.80, "fiber": 0.5, "category": "protein", "price": 120.0, "availability": "Low"},
    {"name": "Sunflower Cake", "protein": 28.0, "energy": 2200, "calcium": 0.40, "phosphorus": 1.00, "fiber": 12.0, "category": "protein", "price": 35.0, "availability": "Medium"},
    {"name": "Oyster Shell", "protein": 0.0, "energy": 0, "calcium": 38.00, "phosphorus": 0.10, "fiber": 0.0, "category": "mineral", "price": 8.0, "availability": "High"},
    {"name": "Bone Meal", "protein": 20.0, "energy": 0, "calcium": 24.00, "phosphorus": 12.00, "fiber": 0.0, "category": "mineral", "price": 12.0, "availability": "Medium"},
    {"name": "Cottonseed Cake", "protein": 35.0, "energy": 2800, "calcium": 0.20, "phosphorus": 1.10, "fiber": 14.0, "category": "protein", "price": 25.0, "availability": "Low"},
    {"name": "Palm Kernel Cake", "protein": 18.0, "energy": 1800, "calcium": 0.30, "phosphorus": 0.80, "fiber": 20.0, "category": "fiber", "price": 15.0, "availability": "High"}
]

def load_ingredients_from_db(conn):
    df = pd.read_sql_query("SELECT * FROM ingredients", conn)
    if df.empty:
        # populate defaults
        cur = conn.cursor()
        for ing in DEFAULT_INGREDIENTS:
            cur.execute(
                "INSERT OR IGNORE INTO ingredients (name,protein,energy,calcium,phosphorus,fiber,category,price,availability) VALUES (?,?,?,?,?,?,?,?,?)",
                (ing['name'], ing['protein'], ing['energy'], ing['calcium'], ing['phosphorus'], ing['fiber'], ing['category'], ing['price'], ing['availability'])
            )
        conn.commit()
        df = pd.read_sql_query("SELECT * FROM ingredients", conn)
    return df

def save_ingredient(conn, row):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO ingredients (id, name, protein, energy, calcium, phosphorus, fiber, category, price, availability)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (row.get('id'), row['name'], row['protein'], row['energy'], row['calcium'], row['phosphorus'], row['fiber'], row['category'], row['price'], row['availability']))
    conn.commit()

# -----------------------
# Utilities: similarity, preprocess
# -----------------------
def preprocess_for_similarity(df):
    """
    Return original dataframe and a scaled copy for nutrient similarity.
    Keeps original values for display.
    """
    nutrients = ['protein', 'energy', 'calcium', 'phosphorus', 'fiber']
    df_copy = df.copy()
    if SKLEARN_OK:
        scaler = MinMaxScaler()
        df_copy[nutrients] = scaler.fit_transform(df_copy[nutrients].fillna(0))
    else:
        # simple min-max fallback
        for c in nutrients:
            col = df_copy[c].astype(float).fillna(0)
            mn, mx = col.min(), col.max()
            if mx - mn == 0:
                df_copy[c] = 0.0
            else:
                df_copy[c] = (col - mn) / (mx - mn)
    return df, df_copy

# import pandas as pd

def find_substitutes(name, df, top_n=5, same_category=False):
    """
    Find substitute ingredients for a given ingredient name.

    Parameters:
        name (str)        : Ingredient name to find substitutes for.
        df (pd.DataFrame) : DataFrame containing ingredient data.
        top_n (int)       : Number of top substitutes to return.
        same_category (bool) : If True, only consider same-category ingredients.

    Returns:
        pd.DataFrame : Substitute ingredient list with similarity scores.
    """
    # Ensure required columns exist in DataFrame
    required_cols = ['name', 'protein_r', 'energy_r', 'calcium_r',
                     'phosphorus_r', 'fiber_r', 'category', 'price', 'availability']
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NA  # Create column with NaN if missing
            print(f"⚠️ Warning: '{col}' column missing in input data. Filled with NaN.")

    # Get base ingredient row
    base = df[df['name'] == name]
    if base.empty:
        print(f"❌ Error: Ingredient '{name}' not found in dataset.")
        return pd.DataFrame()

    base = base.iloc[0]

    # Optionally filter by category
    candidates = df[df['name'] != name]
    if same_category and pd.notna(base['category']):
        candidates = candidates[candidates['category'] == base['category']]

    # Calculate similarity score
    for nutrient in ['protein_r', 'energy_r', 'calcium_r', 'phosphorus_r', 'fiber_r']:
        if nutrient in candidates.columns:
            candidates[f'{nutrient}_diff'] = (candidates[nutrient] - base[nutrient]).abs()

    candidates['similarity'] = 100 - (
        candidates[[f'{n}_diff' for n in ['protein_r', 'energy_r', 'calcium_r', 'phosphorus_r', 'fiber_r']]]
        .sum(axis=1, skipna=True)
    )

    # Sort and select top_n
    result = candidates.sort_values(by='similarity', ascending=False).head(top_n)

    # Final column order (safe selection)
    final_cols = [c for c in ['name', 'category', 'protein_r', 'energy_r', 
                              'calcium_r', 'phosphorus_r', 'fiber_r', 
                              'price', 'availability', 'similarity'] if c in result.columns]

    
    return result[final_cols].reset_index(drop=True)
# -----------------------
# Cost optimizer
# -----------------------
def optimize_cost(ingredients_df, targets, bounds=None, max_per_ingredient=1.0):
    """
    Solve min cost mix satisfying nutrient targets (targets are per kg values, e.g. protein%).
    If scipy.linprog available, uses LP:
      - variables: fraction of each ingredient in final mix (sum to 1)
      - minimize sum(price_i * fraction_i)
      - constraints: sum(fraction_i * nutrient_i) >= target_nutrient
    Fallback: greedy choose cheapest ingredients while meeting constraints approximately.
    """
    ing = ingredients_df.reset_index(drop=True)
    n = len(ing)
    prices = ing['price'].astype(float).values
    nutrients_matrix = ing[['protein','energy','calcium','phosphorus','fiber']].astype(float).values.T  # shape (nutrients, n)

    # Build constraints: A_ub x <= b_ub ; we need -A x <= -targets  (for >= constraints)
    A_ub = -nutrients_matrix  # each row: -nutrient_i for all ingredients
    b_ub = -np.array([targets['protein'], targets['energy'], targets['calcium'], targets['phosphorus'], targets['fiber']])

    # equality: sum fractions = 1
    A_eq = np.ones((1,n))
    b_eq = np.array([1.0])

    bounds_list = [(0.0, max_per_ingredient) for _ in range(n)]
    if SCIPY_OK:
        res = linprog(prices, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds_list, method='highs')
        if res.success:
            fractions = res.x
            solution = ing.copy()
            solution['fraction'] = fractions
            solution['contribution_protein'] = solution['fraction'] * solution['protein']
            # compute achieved nutrients
            achieved = {}
            nutrients = ['protein','energy','calcium','phosphorus','fiber']
            for i, nut in enumerate(nutrients):
                achieved[nut] = float(np.sum(solution['fraction'] * solution[nut]))
            total_cost_per_kg = float(np.sum(solution['fraction'] * solution['price']))
            return {'success': True, 'solution': solution[solution['fraction']>1e-6], 'achieved': achieved, 'cost_per_kg': total_cost_per_kg}
        else:
            return {'success': False, 'message': res.message}
    else:
        # greedy fallback: satisfy highest-priority nutrient first by selecting cheapest ingredient that supplies it
        sol = []
        remain_targets = targets.copy()
        fractions = np.zeros(n)
        # sort by price ascending
        idx_sorted = np.argsort(prices)
        # simple loop: assign fraction of cheapest ingredient until targets met or sum to 1
        fraction_remaining = 1.0
        for idx in idx_sorted:
            if fraction_remaining <= 0:
                break
            ing_provide = { 'protein': ing.loc[idx, 'protein'], 'energy': ing.loc[idx,'energy'], 'calcium': ing.loc[idx,'calcium'],
                           'phosphorus': ing.loc[idx,'phosphorus'], 'fiber': ing.loc[idx,'fiber'] }
            # naive fraction: proportionally fill based on protein requirement as proxy
            # compute a fraction that if fully used would supply missing protein (as example)
            if remain_targets['protein'] > 0 and ing_provide['protein']>0:
                need = remain_targets['protein']
                frac = min(fraction_remaining, need / ing_provide['protein'])
            else:
                frac = min(0.5, fraction_remaining)  # some default
            fractions[idx] = frac
            fraction_remaining -= frac
            # update remaining targets
            for k in remain_targets:
                remain_targets[k] = max(0.0, remain_targets[k] - frac * ing_provide[k])
        if fraction_remaining > 0:
            # distribute remaining evenly among ingredients
            fractions += fraction_remaining / n
        solution = ing.copy()
        solution['fraction'] = fractions
        achieved = {}
        nutrients = ['protein','energy','calcium','phosphorus','fiber']
        for nut in nutrients:
            achieved[nut] = float(np.sum(solution['fraction'] * solution[nut]))
        total_cost_per_kg = float(np.sum(solution['fraction'] * solution['price']))
        return {'success': True, 'solution': solution[solution['fraction']>1e-6], 'achieved': achieved, 'cost_per_kg': total_cost_per_kg, 'note': 'greedy fallback used'}

# -----------------------
# Streamlit UI
# -----------------------
def show_ingredient_manager(conn):
    st.header("Ingredients (Local DB)")
    df = load_ingredients_from_db(conn)
    st.write("You can edit ingredient prices & availability. Upload CSV to add more.")
    st.dataframe(df[['id','name','category','protein','energy','calcium','phosphorus','fiber','price','availability']])

    with st.expander("Add / Edit Ingredient"):
        st.info("If editing existing ingredient, include its id to replace.")
        with st.form("ingredient_form"):
            col1, col2 = st.columns(2)
            with col1:
                iid = st.text_input("id (leave blank for new)")
                name = st.text_input("Name", value="Maize")
                category = st.selectbox("Category", ["energy","protein","fiber","mineral","other"])
                price = st.number_input("Price (KES/kg)", min_value=0.0, value=10.0)
                availability = st.selectbox("Availability", ["High","Medium","Low"])
            with col2:
                protein = st.number_input("Protein (%)", min_value=0.0, value=8.5)
                energy = st.number_input("Energy (kcal/kg)", min_value=0.0, value=3400.0)
                calcium = st.number_input("Calcium (%)", min_value=0.0, value=0.02)
                phosphorus = st.number_input("Phosphorus (%)", min_value=0.0, value=0.25)
                fiber = st.number_input("Fiber (%)", min_value=0.0, value=2.0)
            submitted = st.form_submit_button("Save Ingredient")
            if submitted:
                row = {
                    'id': int(iid) if iid.strip() else None,
                    'name': name,
                    'protein': protein,
                    'energy': energy,
                    'calcium': calcium,
                    'phosphorus': phosphorus,
                    'fiber': fiber,
                    'category': category,
                    'price': price,
                    'availability': availability
                }
                save_ingredient(conn, row)
                st.success("Saved to DB. Refresh table to see changes.")

    with st.expander("Upload ingredients CSV (columns: name,protein,energy,calcium,phosphorus,fiber,category,price,availability)"):
        uploaded = st.file_uploader("CSV", type=['csv'])
        if uploaded:
            new_df = pd.read_csv(uploaded)
            for _, r in new_df.iterrows():
                save_ingredient(conn, r.to_dict())
            st.success("Uploaded ingredients into DB. Refresh table.")

def feed_calculator_ui(conn):
    st.header("Feed Calculator")
    df = load_ingredients_from_db(conn)
    st.info("Create a feed recipe by selecting ingredients and target profile. The optimizer will try to meet targets at minimum cost.")
    bird_type = st.selectbox("Bird type", ["Broiler (meat)", "Layer (eggs)", "Grower", "Starter"])
    age_weeks = st.number_input("Age (weeks)", min_value=0, max_value=52, value=3)
    num_birds = st.number_input("Number of birds", min_value=1, value=10)
    target_prod = st.selectbox("Target production", ["Meat", "Eggs", "General"])

    # Target nutrient profiles (per kg)
    st.markdown("**Target nutrient profile (per kg feed)**")
    default_targets_map = {
        "Broiler (meat)": {'protein':20.0, 'energy':3000.0, 'calcium':0.9, 'phosphorus':0.45, 'fiber':6.0},
        "Layer (eggs)": {'protein':18.0, 'energy':2750.0, 'calcium':3.5, 'phosphorus':0.45, 'fiber':6.0},
        "Grower": {'protein':16.0, 'energy':2900.0, 'calcium':0.9, 'phosphorus':0.45, 'fiber':6.0},
        "Starter": {'protein':22.0, 'energy':3100.0, 'calcium':1.0, 'phosphorus':0.5, 'fiber':5.0}
    }
    def_targets = default_targets_map.get(bird_type, default_targets_map['Grower'])
    col1, col2, col3 = st.columns(3)
    with col1:
        t_protein = st.number_input("Protein (%)", value=def_targets['protein'])
        t_energy = st.number_input("Energy (kcal/kg)", value=def_targets['energy'])
    with col2:
        t_calcium = st.number_input("Calcium (%)", value=def_targets['calcium'])
        t_phosphorus = st.number_input("Phosphorus (%)", value=def_targets['phosphorus'])
    with col3:
        t_fiber = st.number_input("Fiber (%)", value=def_targets['fiber'])

    # ingredient selection & avail filter
    st.markdown("**Select available ingredients to include in mix**")
    avail_names = df['name'].tolist()
    selected = st.multiselect("Available ingredients", options=avail_names, default=avail_names[:6])
    include_df = df[df['name'].isin(selected)].reset_index(drop=True)
    st.write(f"{len(include_df)} ingredients selected")

    max_per_ing = st.slider("Max fraction per ingredient", 0.1, 1.0, 0.9)
    if st.button("Compute optimized feed (cost-minimized)"):
        targets = {'protein': t_protein, 'energy': t_energy, 'calcium': t_calcium, 'phosphorus': t_phosphorus, 'fiber': t_fiber}
        if include_df.empty:
            st.warning("Select at least one ingredient")
        else:
            with st.spinner("Optimizing... (offline)"):
                res = optimize_cost(include_df, targets, max_per_ingredient=max_per_ing)
                if not res.get('success'):
                    st.error("Optimization failed: " + str(res.get('message','')))
                else:
                    sol = res['solution'].copy()
                    sol['percent'] = sol['fraction'] * 100
                    st.success(f"Estimated cost per kg: KES {res['cost_per_kg']:.2f}")
                    st.dataframe(sol[['name','percent','protein','energy','calcium','phosphorus','fiber','price']].round(3))
                    st.subheader("Achieved nutrient profile")
                    achieved = res['achieved']
                    ach_df = pd.DataFrame([achieved])
                    st.table(ach_df.T.rename(columns={0:'achieved'}).round(3))
                    # offer to save as batch
                    if st.button("Save as batch (Nutritional Tracker)"):
                        # compute totals per qty=1kg for now, let user set qty next
                        qty = st.number_input("Batch quantity (kg)", min_value=1.0, value=50.0)
                        total_protein = achieved['protein'] * qty / 100.0 if achieved['protein'] > 5 else achieved['protein'] * qty  # ensure consistent units: note our targets are % so treat as %; keep simple
                        # store simplified totals (we store achieved as-is)
                        cur = conn.cursor()
                        recipe = sol[['name','percent']].to_json(orient='records')
                        cur.execute("""INSERT INTO batches (name,date,recipe,qty_kg,total_protein,total_calcium,total_energy,total_vitamins,notes)
                                       VALUES (?,?,?,?,?,?,?,?,?)""",
                                    (f"{bird_type} mix {dt.date.today()}", str(dt.date.today()), recipe, qty,
                                     achieved['protein'], achieved['calcium'], achieved['energy'], 0.0, f"Auto-saved mix for {bird_type}"))
                        conn.commit()
                        st.success("Batch saved.")

def ingredient_matcher_ui(conn):
    st.header("Local Ingredient Matcher")
    df = load_ingredients_from_db(conn)
    names = df['name'].tolist()
    name = st.selectbox("Ingredient to replace", names)
    same_cat = st.checkbox("Limit to same category", True)
    top_n = st.slider("Number of substitutes", 1, 6, 3)
    if st.button("Find substitutes"):
        with st.spinner("Finding substitutes..."):
            subs = find_substitutes(name, df, top_n=top_n, same_category=same_cat)
            if subs.empty:
                st.warning("No substitutes found")
            else:
                for i, r in subs.iterrows():
                    st.markdown(f"**{r['name']}** — similarity {r['similarity']:.2f} — price KES {r['price']}/kg — avail: {r['availability']}")
                # show comparison table (original vs substitutes) using subset formatting
                target = df[df['name']==name].iloc[0]
                comp = pd.DataFrame({
                    'Nutrient': ['Protein (%)','Energy (kcal/kg)','Calcium (%)','Phosphorus (%)','Fiber (%)'],
                    'Original': [target['protein'], target['energy'], target['calcium'], target['phosphorus'], target['fiber']]
                })
                for _, sub in subs.iterrows():
                    comp[sub['name']] = [sub['protein'], sub['energy'], sub['calcium'], sub['phosphorus'], sub['fiber']]
                st.dataframe(comp.style.format("{:.2f}", subset=comp.columns[1:]), use_container_width=True)

def nutritional_tracker_ui(conn):
    st.header("Nutritional Tracker — Batches")
    cur = conn.cursor()
    if st.button("Refresh batches"):
        pass
    batches = pd.read_sql_query("SELECT * FROM batches ORDER BY date DESC", conn)
    if batches.empty:
        st.info("No batches logged yet.")
    else:
        st.dataframe(batches[['id','name','date','qty_kg','total_protein','total_calcium','total_energy']].round(3))

    with st.expander("Add manual batch"):
        with st.form("manual_batch"):
            name = st.text_input("Batch name", value=f"Batch {dt.date.today()}")
            date = st.date_input("Date", value=dt.date.today())
            qty = st.number_input("Quantity (kg)", min_value=1.0, value=50.0)
            protein = st.number_input("Protein (%)", min_value=0.0, value=18.0)
            calcium = st.number_input("Calcium (%)", min_value=0.0, value=1.0)
            energy = st.number_input("Energy (kcal/kg)", min_value=0.0, value=2900.0)
            vitamins = st.number_input("Vitamins (IU total/kg)", min_value=0.0, value=0.0)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add batch")
            if submitted:
                cur.execute("""INSERT INTO batches (name,date,recipe,qty_kg,total_protein,total_calcium,total_energy,total_vitamins,notes)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (name, str(date), "manual", qty, protein, calcium, energy, vitamins, notes))
                conn.commit()
                st.success("Batch added")

    if not batches.empty:
        # export
        csv = batches.to_csv(index=False)
        st.download_button("Download batches CSV", csv, file_name="batches.csv")

def growth_scheduler_ui(conn):
    st.header("Growth Stage Scheduler")
    st.write("Enter hatch date to get current stage and alerts.")
    hatch_date = st.date_input("Hatch Date", value=dt.date.today() - dt.timedelta(weeks=2))
    today = dt.date.today()
    age_days = (today - hatch_date).days
    st.write(f"Bird age: **{age_days} days**")
    # simple schedule
    if age_days < 14:
        stage = "Starter"
        next_change = hatch_date + dt.timedelta(days=14)
    elif 14 <= age_days < 28:
        stage = "Grower"
        next_change = hatch_date + dt.timedelta(days=28)
    else:
        stage = "Finisher"
        next_change = None

    st.success(f"Current recommended stage: **{stage}**")
    if next_change:
        days_left = (next_change - today).days
        if days_left <= 3:
            st.warning(f"Change feed soon! Next stage change in {days_left} day(s) on {next_change}")
        else:
            st.info(f"Next stage change: {next_change} ({days_left} days left)")

def data_logging_ui(conn):
    st.header("Data Logging & Analytics")
    st.write("Record weekly weights and mortalities for simple analytics.")
    with st.form("flock_log"):
        flock = st.text_input("Flock name", value="Flock A")
        date = st.date_input("Date", value=dt.date.today())
        avg_weight = st.number_input("Avg weight (g)", min_value=0.0, value=1200.0)
        mortality = st.number_input("Mortality (count)", min_value=0, value=0)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Log entry")
        if submitted:
            cur = conn.cursor()
            cur.execute("INSERT INTO flock_logs (flock_name,date,avg_weight_g,mortality,notes) VALUES (?,?,?,?,?)",
                        (flock, str(date), avg_weight, mortality, notes))
            conn.commit()
            st.success("Logged.")

    logs = pd.read_sql_query("SELECT * FROM flock_logs ORDER BY date DESC", conn)
    if not logs.empty:
        st.dataframe(logs[['id','flock_name','date','avg_weight_g','mortality']])
        csv = logs.to_csv(index=False)
        st.download_button("Download flock logs CSV", csv, file_name="flock_logs.csv")

# -----------------------
# Main
# -----------------------
def main():
    st.set_page_config(page_title="Smart Poultry Feed Planner (Offline MVP)", layout="wide")
    st.title("🌾 Smart Poultry Feed Planner — Offline MVP")
    st.markdown("Built for low-connectivity rural use. Data stored locally in `smart_poultry.db`.")

    conn = init_db()

    tabs = st.tabs(["Ingredients", "Feed Calculator", "Ingredient Matcher", "Nutritional Tracker", "Growth Scheduler", "Data Logging"])
    with tabs[0]:
        show_ingredient_manager(conn)
    with tabs[1]:
        feed_calculator_ui(conn)
    with tabs[2]:
        ingredient_matcher_ui(conn)
    with tabs[3]:
        nutritional_tracker_ui(conn)
    with tabs[4]:
        growth_scheduler_ui(conn)
    with tabs[5]:
        data_logging_ui(conn)

    st.sidebar.header("Offline notes & tips")
    st.sidebar.write("""
    - This app stores data in `smart_poultry.db` in the same folder.
    - For best cost-optimization install `scipy` (pip install scipy). Without scipy a greedy fallback is used.
    - You can export CSVs from the trackers for backup (transfer via USB).
    - Keep ingredient prices up-to-date for accurate cost optimization.
    """)

if __name__ == "__main__":
    main()
