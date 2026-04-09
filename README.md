# Smart Poultry Feed Planner — Offline MVP

A **data-driven poultry feed formulation and farm management tool** designed for **low-connectivity environments**.
Built using **Streamlit + SQLite**, this application enables farmers, agribusiness operators, and feed formulators to **optimize feed cost, track nutrition, and manage flock performance — entirely offline**.

---

## Overview

The Smart Poultry Feed Planner bridges the gap between:

* **Traditional poultry farming practices**
* **Modern data-driven decision-making**

It provides a **locally deployable system** that supports:

* Feed formulation
* Ingredient substitution
* Nutritional tracking
* Growth scheduling
* Cost optimization
* Farm data logging

---

## Key Features

### 1. Feed Calculator (Cost Optimization Engine)

* Formulate feed mixes based on:

  * Bird type (Broiler, Layer, Starter, Grower)
  * Nutritional targets (protein, energy, calcium, etc.)
* Uses:

  * **Linear Programming (SciPy)** for optimal solutions *(if available)*
  * **Greedy fallback algorithm** (offline-safe)
* Outputs:

  * Ingredient proportions (%)
  * Achieved nutrient profile
  * Cost per kg (KES)

---

### 2. Local Ingredient Matcher

* Finds **nutritionally similar substitutes** for unavailable ingredients
* Uses:

  * Nutrient similarity scoring (cosine similarity / normalized distance)
* Filters:

  * Same-category substitution (e.g., protein → protein)
* Helps mitigate:

  * Supply chain disruptions
  * Price volatility

---

### 3. Nutritional Tracker (Batch Management)

* Save and track feed batches
* Store:

  * Recipe composition
  * Nutritional values
  * Batch quantity
* Export data as CSV for:

  * Reporting
  * Backup
  * External analysis

---

### 4. Growth Stage Scheduler

* Calculates bird age from hatch date
* Automatically determines:

  * Current growth stage (Starter, Grower, Finisher)
  * Upcoming feed transitions
* Provides alerts for:

  * Feed change timing

---

### 5. Data Logging & Analytics

* Record:

  * Average flock weight
  * Mortality rates
* Enables:

  * Performance monitoring
  * Trend analysis (via exported CSV)

---

### 6. Ingredient Management System

* Local database of feed ingredients
* Editable attributes:

  * Nutritional values
  * Price (KES/kg)
  * Availability
* Supports CSV upload for bulk updates

---

##  Tech Stack

| Layer         | Technology              |
| ------------- | ----------------------- |
| Frontend      | Streamlit               |
| Backend Logic | Python                  |
| Database      | SQLite (local file)     |
| Optimization  | SciPy (optional)        |
| ML Utilities  | Scikit-learn (optional) |
| Data Handling | Pandas, NumPy           |

---

##  Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/smart-poultry-feed-planner.git
cd smart-poultry-feed-planner
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Optional (recommended for full functionality):**

```bash
pip install scipy scikit-learn
```

---

##  Running the App

```bash
streamlit run app.py
```

The app will launch in your browser at:

```
http://localhost:8501
```

---

##  Data Storage

* All data is stored locally in:

  ```
  smart_poultry.db
  ```
* No internet connection required
* Ideal for:

  * Rural deployment
  * Offline-first environments

---

##  Project Structure

```
smart-poultry-feed-planner/
│
├── app.py                  # Main Streamlit application
├── smart_poultry.db        # SQLite database (auto-created)
├── requirements.txt
├── README.md
```

---

##  How It Works (Architecture)

### Feed Optimization Model

* Decision variables: ingredient proportions
* Objective: minimize cost
* Constraints:

  * Nutritional requirements (≥ targets)
  * Total mix = 100%

### Fallback Logic

If SciPy is unavailable:

* Uses heuristic (greedy) allocation
* Ensures approximate feasibility

---

##  Example Use Cases

* Smallholder poultry farmers (offline environments)
* Feed distributors optimizing formulation costs
* Agricultural extension officers
* Agri-tech startups building decision support tools
* NGOs supporting rural food systems

---

##  Future Enhancements

*  Mobile-friendly UI (PWA)
*  Cloud sync (Firebase / Supabase)
*  Advanced analytics dashboard
*  AI-based feed recommendations
*  Multi-language support (Swahili, Somali)
*  IoT integration (smart feeders, weight sensors)

---

##  Limitations

* Nutritional targets are simplified (not species-specific precision)
* Greedy optimizer is less accurate than LP
* No real-time market price integration
* Limited micronutrient modeling (vitamins, amino acids)

---

## Contribution

Contributions are welcome. You can:

* Improve optimization models
* Add new ingredient datasets
* Enhance UI/UX
* Integrate APIs or cloud backends

---

## License

MIT License — free to use and modify.

---

## Author

**John Charles Otieno**

---

## Strategic Insight

This project demonstrates:

* **Applied optimization (operations research)**
* **Offline-first system design**
* **Real-world problem solving in emerging markets**
* **Integration of data science into traditional industries**

---
