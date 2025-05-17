from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import sqlite3
import numpy as np
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session

# Database setup
def init_db():
    conn = sqlite3.connect('tnstc.db')
    cursor = conn.cursor()
    
    # Create districts table
    cursor.execute(''' 
    CREATE TABLE IF NOT EXISTS districts (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )
    ''')
    
    # Create routes table
    cursor.execute(''' 
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        distance REAL NOT NULL,
        time REAL NOT NULL,
        UNIQUE(origin, destination)
    )
    ''')
    
    # Create stops table
    cursor.execute(''' 
    CREATE TABLE IF NOT EXISTS stops (
        id INTEGER PRIMARY KEY,
        route_id INTEGER NOT NULL,
        stop_name TEXT NOT NULL,
        stop_order INTEGER NOT NULL,
        FOREIGN KEY (route_id) REFERENCES routes (id)
    )
    ''')

    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')

    # Create tickets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        route_id INTEGER,
        date TEXT NOT NULL,
        seats INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (route_id) REFERENCES routes(id)
    )
    ''')

    # Insert initial data for districts
    districts = [
        (1, "Chennai"),
        (2, "Coimbatore"),
        (3, "Madurai"),
        (4, "Trichy"),
        (5, "Salem"),
        (6, "Erode"),
        (7, "Tirunelveli"),
        (8, "Vellore"),
        (9, "Thanjavur"),
        (10, "Tiruppur"),
        (11, "Cuddalore"),
        (12, "Pondicherry"),
    ]
    
    for district in districts:
        cursor.execute("INSERT OR IGNORE INTO districts (id, name) VALUES (?, ?)", district)

    # Insert initial data for routes
    routes = {
        "Chennai to Coimbatore": {
            "distance": 496,
            "time": 8.5,
            "stops": ["Vellore", "Arcot", "Erode"]
        },
        "Madurai to Trichy": {
            "distance": 142,
            "time": 3.5,
            "stops": ["Dindigul", "Karur"]
        },
        # All other routes remain the same
        # ... [routes code omitted for brevity]
    }
    # Insert route data
    for route_name, route_data in routes.items():
        origin, destination = route_name.split(" to ")
        cursor.execute(
            "INSERT OR IGNORE INTO routes (origin, destination, distance, time) VALUES (?, ?, ?, ?)",
            (origin, destination, route_data["distance"], route_data["time"])
        )
        
        # Get the route_id for foreign key reference
        cursor.execute("SELECT id FROM routes WHERE origin = ? AND destination = ?", (origin, destination))
        route_id = cursor.fetchone()[0]
        
        for stop_order, stop_name in enumerate(route_data["stops"], 1):
            cursor.execute(
                "INSERT OR IGNORE INTO stops (route_id, stop_name, stop_order) VALUES (?, ?, ?)",
                (route_id, stop_name, stop_order)
            )
    
    conn.commit()
    conn.close()

# Initialize database if it doesn't exist
if not os.path.exists('tnstc.db'):
    init_db()

# Helper functions
def get_districts():
    conn = sqlite3.connect('tnstc.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM districts ORDER BY name")
    districts = cursor.fetchall()
    conn.close()
    return districts

def find_route(origin, destination):
    conn = sqlite3.connect('tnstc.db')
    cursor = conn.cursor()
    
    # Try direct route
    cursor.execute(""" 
        SELECT id, distance, time FROM routes 
        WHERE origin = ? AND destination = ?
    """, (origin, destination))
    route = cursor.fetchone()
    
    # Try reverse route if direct route doesn't exist
    if not route:
        cursor.execute(""" 
            SELECT id, distance, time FROM routes 
            WHERE origin = ? AND destination = ?
        """, (destination, origin))
        route = cursor.fetchone()
        if route:
            # Swap origin and destination for display
            origin, destination = destination, origin
    
    if route:
        route_id, distance, time = route
        cursor.execute(""" 
            SELECT stop_name FROM stops 
            WHERE route_id = ? 
            ORDER BY stop_order
        """, (route_id,))
        stops = [stop[0] for stop in cursor.fetchall()]
        
        route_info = {
            "origin": origin,
            "destination": destination,
            "distance": distance,
            "time": time,
            "stops": stops
        }
        conn.close()
        return route_info
    
    conn.close()
    return None

def get_all_routes():
    conn = sqlite3.connect('tnstc.db')
    cursor = conn.cursor()
    cursor.execute(""" 
        SELECT r.origin, r.destination, r.distance, r.time 
        FROM routes r
        ORDER BY r.origin, r.destination
    """)
    routes = cursor.fetchall()
    conn.close()
    return routes

def analyze_routes():
    routes = get_all_routes()
    if not routes:
        return None
    
    distances = np.array([route[2] for route in routes])
    times = np.array([route[3] for route in routes])
    
    analysis = {
        'total_routes': len(routes),
        'avg_distance': np.mean(distances),
        'avg_time': np.mean(times),
        'max_distance': np.max(distances),
        'min_distance': np.min(distances),
        'longest_route': next((f"{routes[i][0]} to {routes[i][1]}" for i in range(len(routes)) if routes[i][2] == np.max(distances)), ""),
        'shortest_route': next((f"{routes[i][0]} to {routes[i][1]}" for i in range(len(routes)) if routes[i][2] == np.min(distances)), "")
    }
    
    return analysis

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('index'))
    else:
        return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    districts = get_districts()
    analysis = analyze_routes()
    return render_template('index.html', districts=districts, analysis=analysis, username=session.get('username'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('tnstc.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            flash("Account created successfully! Please login.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Username already exists. Please choose another.")
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']
        
        conn = sqlite3.connect('tnstc.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password_input):
            session['user_id'] = user[0]
            session['username'] = username
            flash("Login successful!")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash("You have been logged out")
    return redirect(url_for('login'))

@app.route('/find_route', methods=['POST'])
def route_finder():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    origin = request.form.get('origin')
    destination = request.form.get('destination')
    
    if origin == destination:
        return render_template('result.html', error="Origin and destination cannot be the same.")
    
    route_info = find_route(origin, destination)
    
    if route_info:
        return render_template('result.html', route=route_info, username=session.get('username'))
    else:
        return render_template('result.html', error="No route found between these districts.", username=session.get('username'))

@app.route('/routes')
def all_routes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    routes = get_all_routes()
    return render_template('routes.html', routes=routes, username=session.get('username'))

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    analysis = analyze_routes()
    routes = get_all_routes()
    
    # Calculate distances for chart
    route_names = [f"{r[0]} to {r[1]}" for r in routes]
    distances = [r[2] for r in routes]
    times = [r[3] for r in routes]
    
    return render_template('analytics.html', 
                          analysis=analysis, 
                          route_names=route_names,
                          distances=distances,
                          times=times,
                          username=session.get('username'))

@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    districts = get_districts()
    if request.method == 'POST':
        # Make sure the form fields exist before trying to access them
        if 'origin' in request.form and 'destination' in request.form:
            origin = request.form['origin']
            destination = request.form['destination']
            date = request.form['date']
            seats = int(request.form['seats'])

            conn = sqlite3.connect('tnstc.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM routes WHERE origin=? AND destination=?", (origin, destination))
            route = cursor.fetchone()
            route_id = route[0] if route else None

            cursor.execute(
                "INSERT INTO tickets (user_id, origin, destination, route_id, date, seats) VALUES (?, ?, ?, ?, ?, ?)",
                (session['user_id'], origin, destination, route_id, date, seats)
            )
            conn.commit()
            conn.close()
            flash("Ticket booked successfully!")
            return redirect(url_for('my_tickets'))

    return render_template('book_ticket.html', districts=districts, username=session.get('username'))

@app.route('/my_tickets')
def my_tickets():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('tnstc.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.origin, t.destination, t.date, t.seats, r.distance, r.time
        FROM tickets t
        LEFT JOIN routes r ON t.route_id = r.id
        WHERE t.user_id = ?
        ORDER BY t.date DESC
    """, (session['user_id'],))
    
    tickets = cursor.fetchall()
    conn.close()
    
    # Use a different template for viewing tickets
    return render_template('my_tickets.html', tickets=tickets, username=session.get('username'))
    
    return render_template('book_ticket.html', tickets=tickets, username=session.get('username'))
if __name__ == '__main__':
    app.run(debug=True)