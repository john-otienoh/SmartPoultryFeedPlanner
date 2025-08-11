# poultry_auth_system.py
import streamlit as st
import sqlite3
import hashlib
import re
from datetime import datetime

# Database Setup
def init_db():
    conn = sqlite3.connect('poultry_farmers.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS farmers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  full_name TEXT NOT NULL,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  phone TEXT UNIQUE NOT NULL,
                  region TEXT NOT NULL,
                  farm_size TEXT,
                  bird_type TEXT,
                  registration_date TEXT,
                  last_login TEXT)''')
    conn.commit()
    conn.close()

# Security
def hash_password(password, salt="poultry_salt_2023"):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

# Validation
def validate_phone(phone):
    """Validate African phone number formats"""
    return re.match(r'^\+?[0-9]{10,15}$', phone)

def validate_password(password):
    """At least 6 chars with one number and one special char"""
    return re.match(r'^(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{6,}$', password)

# Farmer Registration
def register_farmer():
    st.title("🐔 Smart Poultry Feed Planner")
    st.subheader("New Farmer Registration")
    
    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name", placeholder="John Kamau")
            username = st.text_input("Username", placeholder="john_farm")
            password = st.text_input("Password", type="password", 
                                   help="At least 6 characters with one number and one special character")
            confirm_pass = st.text_input("Confirm Password", type="password")
            
        with col2:
            phone = st.text_input("Phone Number", placeholder="+254712345678")
            region = st.selectbox("Region", 
                                ["Uasin Gishu", "Kiambu", "Nakuru", "Trans Nzoia", "Other"])
            farm_size = st.selectbox("Farm Size", 
                                   ["Small (1-50 birds)", "Medium (51-200)", "Large (200+)"])
            bird_type = st.selectbox("Main Bird Type", 
                                    ["Broilers", "Layers", "Both", "Other"])
        
        agree_terms = st.checkbox("I agree to the Terms of Service and Privacy Policy")
        submitted = st.form_submit_button("Register Account")
        
        if submitted:
            # Validate inputs
            errors = []
            
            if not full_name or len(full_name.split()) < 2:
                errors.append("Please enter your full name")
                
            if not username or len(username) < 4:
                errors.append("Username must be at least 4 characters")
                
            if not validate_password(password):
                errors.append("Password must contain 6+ chars with 1 number and 1 special character")
            elif password != confirm_pass:
                errors.append("Passwords don't match")
                
            if not validate_phone(phone):
                errors.append("Invalid phone number format")
                
            if not agree_terms:
                errors.append("You must accept the terms to register")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                try:
                    conn = sqlite3.connect('poultry_farmers.db')
                    c = conn.cursor()
                    
                    # Check if username or phone exists
                    c.execute("SELECT 1 FROM farmers WHERE username = ? OR phone = ?", 
                             (username, phone))
                    if c.fetchone():
                        st.error("Username or phone number already registered")
                    else:
                        # Insert new farmer
                        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute('''INSERT INTO farmers 
                                     (full_name, username, password, phone, region, 
                                      farm_size, bird_type, registration_date)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (full_name, username, hash_password(password), phone, 
                                  region, farm_size, bird_type, registration_date))
                        conn.commit()
                        
                        st.success("Registration successful! Please login.")
                        st.balloons()
                        st.session_state.show_login = True
                        st.rerun()
                        
                except sqlite3.Error as e:
                    st.error(f"Database error: {str(e)}")
                finally:
                    conn.close()

    if st.button("Already have an account? Login here"):
        st.session_state.show_login = True
        st.rerun()

# Farmer Login
def login_farmer():
    st.title("🐔 Smart Poultry Feed Planner")
    st.subheader("Farmer Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                try:
                    conn = sqlite3.connect('poultry_farmers.db')
                    c = conn.cursor()
                    
                    c.execute('''SELECT id, full_name, username, region, farm_size 
                                FROM farmers 
                                WHERE username = ? AND password = ?''', 
                             (username, hash_password(password)))
                    farmer = c.fetchone()
                    
                    if farmer:
                        # Update last login
                        last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute('''UPDATE farmers 
                                    SET last_login = ? 
                                    WHERE id = ?''', (last_login, farmer[0]))
                        conn.commit()
                        
                        # Set session state
                        st.session_state.authenticated = True
                        st.session_state.current_user = {
                            "id": farmer[0],
                            "full_name": farmer[1],
                            "username": farmer[2],
                            "region": farmer[3],
                            "farm_size": farmer[4]
                        }
                        
                        if remember_me:
                            # In a real app, use secure cookies/tokens
                            st.session_state.remember_me = True
                        
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
                        
                except sqlite3.Error as e:
                    st.error(f"Database error: {str(e)}")
                finally:
                    conn.close()
    
    if st.button("Don't have an account? Register here"):
        st.session_state.show_login = False
        st.rerun()

# Main App
def main():
    init_db()
    
    # Session state setup
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'show_login' not in st.session_state:
        st.session_state.show_login = True
    
    # Page routing
    if st.session_state.authenticated:
        show_dashboard()
    else:
        if st.session_state.show_login:
            login_farmer()
        else:
            register_farmer()

# Dashboard (after login)
def show_dashboard():
    user = st.session_state.current_user
    
    st.title(f"Welcome, {user['full_name']}! 👨‍🌾")
    st.subheader(f"📍 {user['region']} | 🏡 {user['farm_size']}")
    
    st.markdown("""
    ### Your Poultry Management Tools
    - � **Feed Calculator**: Create optimal feed mixes
    - 📈 **Growth Tracker**: Monitor bird development
    - 💰 **Cost Analyzer**: Optimize expenses
    - 🏥 **Health Advisor**: Disease prevention tips
    """)
    
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()

if __name__ == "__main__":
    main()