import os
import json
import sqlite3
import random
import math
import csv
import io
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
app.secret_key = "smart_waste_secret_key_super_secure_2026"

# Database Configuration (SQLite with MySQL Fallback)
USE_MYSQL = False
try:
    import mysql.connector
    try:
        db_test = mysql.connector.connect(
            host="localhost",
            user="root",
            password="inventory@212427",
            database="smart_waste_db",
            connect_timeout=2
        )
        db_test.close()
        USE_MYSQL = True
        print("[DB] Connected to MySQL database 'smart_waste_db'.")
    except Exception as err:
        print(f"[DB Warning] MySQL unavailable ({err}). Using SQLite fallback database.")
except ImportError:
    print("[DB Info] mysql-connector-python not installed. Using SQLite fallback database.")

DB_FILE = os.path.join(os.path.dirname(__file__), "smart_waste.db")

# Campus / City Central Depot coordinates for route optimization
DEPOT = {
    "name": "Central Municipal Waste Depot",
    "latitude": 28.6135,
    "longitude": 77.2085
}


def get_status(waste_level):
    if waste_level <= 50:
        return "Normal"
    elif waste_level <= 80:
        return "Warning"
    else:
        return "Full"


def init_sqlite_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Core dustbins table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dustbins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            latitude REAL DEFAULT 28.6139,
            longitude REAL DEFAULT 77.2090,
            bin_type TEXT DEFAULT 'General Waste',
            capacity_liters INTEGER DEFAULT 120,
            waste_level INTEGER NOT NULL,
            status TEXT NOT NULL,
            collection_status TEXT NOT NULL DEFAULT 'Pending',
            battery_level INTEGER DEFAULT 90,
            signal_rssi INTEGER DEFAULT -65,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check and add missing columns for existing SQLite DBs
    cursor.execute("PRAGMA table_info(dustbins)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "latitude" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN latitude REAL DEFAULT 28.6139")
    if "longitude" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN longitude REAL DEFAULT 77.2090")
    if "bin_type" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN bin_type TEXT DEFAULT 'General Waste'")
    if "capacity_liters" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN capacity_liters INTEGER DEFAULT 120")
    if "battery_level" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN battery_level INTEGER DEFAULT 90")
    if "signal_rssi" not in columns:
        cursor.execute("ALTER TABLE dustbins ADD COLUMN signal_rssi INTEGER DEFAULT -65")

    # Users & Auth Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Telemetry time-series log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dustbin_id INTEGER NOT NULL,
            waste_level INTEGER NOT NULL,
            battery_level INTEGER DEFAULT 90,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Collection audit log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dustbin_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            waste_level_before INTEGER NOT NULL,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Citizen Incident Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS citizen_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dustbin_id INTEGER,
            location_name TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT,
            reporter_name TEXT NOT NULL,
            reporter_contact TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Seed Default Users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ("Admin Operations Manager", "admin@smartwaste.com", generate_password_hash("admin123"), "admin"),
            ("Collection Driver Alex", "driver@smartwaste.com", generate_password_hash("driver123"), "driver"),
            ("Resident Citizen Sam", "citizen@smartwaste.com", generate_password_hash("citizen123"), "citizen")
        ]
        for name, email, pwd, role in default_users:
            cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)", (name, email, pwd, role))
        conn.commit()

    # Seed Dustbins Data if empty
    cursor.execute("SELECT COUNT(*) FROM dustbins")
    if cursor.fetchone()[0] == 0:
        json_path = os.path.join(os.path.dirname(__file__), "waste_data.json")
        initial_bins = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    initial_bins = data.get("dustbins", [])
            except Exception as e:
                print(f"Error loading waste_data.json: {e}")

        if not initial_bins:
            initial_bins = [
                {"id": 1, "location": "Main Entrance Gate", "latitude": 28.6139, "longitude": 77.2090, "bin_type": "General Waste", "capacity_liters": 120, "waste_level": 85, "battery_level": 92, "signal_rssi": -65},
                {"id": 2, "location": "Central Canteen", "latitude": 28.6148, "longitude": 77.2099, "bin_type": "Organic Waste", "capacity_liters": 150, "waste_level": 70, "battery_level": 88, "signal_rssi": -70},
                {"id": 3, "location": "Central Library", "latitude": 28.6155, "longitude": 77.2082, "bin_type": "Recyclable Paper", "capacity_liters": 100, "waste_level": 94, "battery_level": 95, "signal_rssi": -58},
                {"id": 4, "location": "IT & Engineering Block", "latitude": 28.6162, "longitude": 77.2105, "bin_type": "E-Waste & Batteries", "capacity_liters": 80, "waste_level": 45, "battery_level": 79, "signal_rssi": -72},
                {"id": 5, "location": "Sports Complex Grounds", "latitude": 28.6128, "longitude": 77.2112, "bin_type": "General Waste", "capacity_liters": 120, "waste_level": 30, "battery_level": 98, "signal_rssi": -62},
                {"id": 6, "location": "Student Activity Center", "latitude": 28.6142, "longitude": 77.2075, "bin_type": "Recyclable Plastic", "capacity_liters": 100, "waste_level": 88, "battery_level": 84, "signal_rssi": -68}
            ]

        for b in initial_bins:
            w_level = b.get("waste_level", 0)
            status = get_status(w_level)
            cursor.execute("""
                INSERT INTO dustbins (id, location, latitude, longitude, bin_type, capacity_liters, waste_level, status, collection_status, battery_level, signal_rssi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
            """, (
                b.get("id"),
                b.get("location", f"Dustbin {b.get('id')}"),
                b.get("latitude", 28.6139),
                b.get("longitude", 77.2090),
                b.get("bin_type", "General Waste"),
                b.get("capacity_liters", 120),
                w_level,
                status,
                b.get("battery_level", 90),
                b.get("signal_rssi", -65)
            ))
            cursor.execute("""
                INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
                VALUES (?, ?, ?)
            """, (b.get("id"), w_level, b.get("battery_level", 90)))
        conn.commit()
    conn.close()


if not USE_MYSQL:
    init_sqlite_db()


def get_db_connection():
    if USE_MYSQL:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="inventory@212427",
            database="smart_waste_db"
        )
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn


def get_waste_data():
    connection = get_db_connection()
    if USE_MYSQL:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, location, latitude, longitude, bin_type, capacity_liters,
                   waste_level, status, collection_status, battery_level, signal_rssi, last_updated
            FROM dustbins
            ORDER BY id ASC
        """)
        dustbins = cursor.fetchall()
        cursor.close()
        connection.close()
    else:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, location, latitude, longitude, bin_type, capacity_liters,
                   waste_level, status, collection_status, battery_level, signal_rssi, last_updated
            FROM dustbins
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()
        dustbins = [dict(row) for row in rows]
        cursor.close()
        connection.close()

    for dustbin in dustbins:
        dustbin["status"] = get_status(dustbin["waste_level"])

    return dustbins


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Authentication & Session Helpers
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    connection = get_db_connection()
    cursor = connection.cursor()
    if USE_MYSQL:
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
    else:
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
    cursor.close()
    connection.close()
    return dict(user) if user else None


# Multi-Portal Routes
@app.route("/")
def home():
    user = get_current_user()
    return render_template("index.html", user=user)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()
        cursor = connection.cursor()
        if USE_MYSQL:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        else:
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            user = dict(row) if row else None
        cursor.close()
        connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("dashboard"))
            elif user["role"] == "driver":
                return redirect(url_for("driver_portal"))
            else:
                return redirect(url_for("citizen_report"))
        else:
            return render_template("login.html", error="Invalid email or password credentials.")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "citizen")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        pwd_hash = generate_password_hash(password)
        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            if USE_MYSQL:
                cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)", (name, email, pwd_hash, role))
                session["user_id"] = cursor.lastrowid
            else:
                cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)", (name, email, pwd_hash, role))
                session["user_id"] = cursor.lastrowid
            connection.commit()
            cursor.close()
            connection.close()

            session["user_name"] = name
            session["user_role"] = role

            if role == "admin":
                return redirect(url_for("dashboard"))
            elif role == "driver":
                return redirect(url_for("driver_portal"))
            else:
                return redirect(url_for("citizen_report"))
        except Exception as e:
            cursor.close()
            connection.close()
            return render_template("register.html", error="An account with this email already exists.")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    dustbins = get_waste_data()
    return render_template("dashboard.html", dustbins=dustbins, depot=DEPOT, user=user)


@app.route("/driver")
def driver_portal():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    dustbins = get_waste_data()
    return render_template("driver.html", dustbins=dustbins, depot=DEPOT, user=user)


@app.route("/report")
def citizen_report():
    user = get_current_user()
    dustbins = get_waste_data()
    return render_template("report.html", dustbins=dustbins, user=user)


@app.route("/simulator")
def virtual_simulator():
    user = get_current_user()
    dustbins = get_waste_data()
    return render_template("simulator.html", dustbins=dustbins, user=user)


@app.route("/collect/<int:dustbin_id>", methods=["POST"])
def collect_dustbin(dustbin_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("SELECT location, waste_level FROM dustbins WHERE id = %s", (dustbin_id,))
        row = cursor.fetchone()
    else:
        cursor.execute("SELECT location, waste_level FROM dustbins WHERE id = ?", (dustbin_id,))
        row = cursor.fetchone()

    waste_level_before = row["waste_level"] if row else 0
    location = row["location"] if row else f"Dustbin {dustbin_id}"

    if USE_MYSQL:
        cursor.execute("""
            UPDATE dustbins
            SET collection_status = 'Collected',
                waste_level = 0,
                status = 'Normal',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (dustbin_id,))
        cursor.execute("""
            INSERT INTO collection_logs (dustbin_id, location, waste_level_before)
            VALUES (%s, %s, %s)
        """, (dustbin_id, location, waste_level_before))
        cursor.execute("""
            INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
            VALUES (%s, 0, 95)
        """, (dustbin_id,))
    else:
        cursor.execute("""
            UPDATE dustbins
            SET collection_status = 'Collected',
                waste_level = 0,
                status = 'Normal',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (dustbin_id,))
        cursor.execute("""
            INSERT INTO collection_logs (dustbin_id, location, waste_level_before)
            VALUES (?, ?, ?)
        """, (dustbin_id, location, waste_level_before))
        cursor.execute("""
            INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
            VALUES (?, 0, 95)
        """, (dustbin_id,))

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "message": f"Dustbin {dustbin_id} ({location}) marked as collected successfully!",
        "dustbin_id": dustbin_id
    })


@app.route("/api/dustbins")
def api_dustbins():
    dustbins = get_waste_data()
    return jsonify({
        "dustbins": dustbins,
        "depot": DEPOT
    })


@app.route("/api/update-dustbin", methods=["POST"])
def update_dustbin():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data received"}), 400

    dustbin_id = data.get("id")
    waste_level = data.get("waste_level")
    battery_level = data.get("battery_level", random.randint(75, 99))

    if dustbin_id is None or waste_level is None:
        return jsonify({"success": False, "message": "id and waste_level are required"}), 400

    try:
        dustbin_id = int(dustbin_id)
        waste_level = int(waste_level)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "id and waste_level must be numbers"}), 400

    if waste_level < 0 or waste_level > 100:
        return jsonify({"success": False, "message": "Waste level must be between 0 and 100"}), 400

    status = get_status(waste_level)
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            UPDATE dustbins
            SET waste_level = %s,
                status = %s,
                battery_level = %s,
                collection_status = 'Pending',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (waste_level, status, battery_level, dustbin_id))
        connection.commit()
        rows_updated = cursor.rowcount
        cursor.execute("""
            INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
            VALUES (%s, %s, %s)
        """, (dustbin_id, waste_level, battery_level))
        connection.commit()
    else:
        cursor.execute("""
            UPDATE dustbins
            SET waste_level = ?,
                status = ?,
                battery_level = ?,
                collection_status = 'Pending',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (waste_level, status, battery_level, dustbin_id))
        connection.commit()
        rows_updated = cursor.rowcount
        cursor.execute("""
            INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
            VALUES (?, ?, ?)
        """, (dustbin_id, waste_level, battery_level))
        connection.commit()

    cursor.close()
    connection.close()

    if rows_updated == 0:
        return jsonify({"success": False, "message": "Dustbin not found"}), 404

    return jsonify({
        "success": True,
        "message": "Dustbin data updated successfully",
        "dustbin_id": dustbin_id,
        "waste_level": waste_level,
        "status": status
    })


@app.route("/api/dustbin/add", methods=["POST"])
def add_dustbin():
    data = request.get_json()
    if not data or not data.get("location"):
        return jsonify({"success": False, "message": "Location name is required"}), 400

    location = data.get("location").strip()
    latitude = float(data.get("latitude", 28.6139 + random.uniform(-0.005, 0.005)))
    longitude = float(data.get("longitude", 77.2090 + random.uniform(-0.005, 0.005)))
    bin_type = data.get("bin_type", "General Waste")
    capacity_liters = int(data.get("capacity_liters", 120))
    waste_level = int(data.get("waste_level", random.randint(20, 60)))
    status = get_status(waste_level)
    battery_level = random.randint(80, 100)
    signal_rssi = random.randint(-75, -55)

    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            INSERT INTO dustbins (location, latitude, longitude, bin_type, capacity_liters, waste_level, status, collection_status, battery_level, signal_rssi)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending', %s, %s)
        """, (location, latitude, longitude, bin_type, capacity_liters, waste_level, status, battery_level, signal_rssi))
        connection.commit()
        new_id = cursor.lastrowid
    else:
        cursor.execute("""
            INSERT INTO dustbins (location, latitude, longitude, bin_type, capacity_liters, waste_level, status, collection_status, battery_level, signal_rssi)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """, (location, latitude, longitude, bin_type, capacity_liters, waste_level, status, battery_level, signal_rssi))
        connection.commit()
        new_id = cursor.lastrowid

    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "message": f"Dustbin '{location}' registered successfully!",
        "id": new_id
    })


@app.route("/api/dustbin/<int:dustbin_id>", methods=["DELETE"])
def delete_dustbin(dustbin_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("DELETE FROM dustbins WHERE id = %s", (dustbin_id,))
    else:
        cursor.execute("DELETE FROM dustbins WHERE id = ?", (dustbin_id,))

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"success": True, "message": f"Dustbin #{dustbin_id} decommissioned successfully."})


@app.route("/api/route-optimization")
def route_optimization():
    dustbins = get_waste_data()
    targets = [b for b in dustbins if b["waste_level"] >= 50 or b["collection_status"] == "Pending"]

    if not targets:
        return jsonify({
            "success": True,
            "message": "All bins are clean. No collection route required!",
            "route": [],
            "total_distance_km": 0,
            "estimated_time_mins": 0,
            "fuel_saved_liters": 0
        })

    unvisited = targets.copy()
    current_lat = DEPOT["latitude"]
    current_lon = DEPOT["longitude"]
    route = []
    total_distance = 0.0

    stop_number = 1
    while unvisited:
        nearest_bin = None
        min_dist = float("inf")
        for b in unvisited:
            dist = haversine_distance(current_lat, current_lon, b["latitude"], b["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest_bin = b

        if nearest_bin:
            total_distance += min_dist
            current_lat = nearest_bin["latitude"]
            current_lon = nearest_bin["longitude"]
            nearest_bin["stop_number"] = stop_number
            nearest_bin["distance_from_prev_km"] = round(min_dist, 2)
            route.append(nearest_bin)
            unvisited.remove(nearest_bin)
            stop_number += 1

    return_dist = haversine_distance(current_lat, current_lon, DEPOT["latitude"], DEPOT["longitude"])
    total_distance += return_dist
    estimated_time = round((len(route) * 8) + (total_distance * 2), 1)
    fuel_saved = round((len(dustbins) - len(route)) * 0.45, 2)

    return jsonify({
        "success": True,
        "depot": DEPOT,
        "route": route,
        "bins_to_collect": len(route),
        "total_distance_km": round(total_distance, 2),
        "estimated_time_mins": estimated_time,
        "fuel_saved_liters": fuel_saved
    })


# AI Predictive Fill Forecasting Engine
@app.route("/api/predictions")
def get_predictions():
    dustbins = get_waste_data()
    predictions = []
    connection = get_db_connection()
    cursor = connection.cursor()

    for bin_item in dustbins:
        bin_id = bin_item["id"]
        # Fetch last 5 telemetry logs
        if USE_MYSQL:
            cursor.execute("SELECT waste_level, recorded_at FROM telemetry_logs WHERE dustbin_id = %s ORDER BY id DESC LIMIT 5", (bin_id,))
            logs = cursor.fetchall()
        else:
            cursor.execute("SELECT waste_level, recorded_at FROM telemetry_logs WHERE dustbin_id = ? ORDER BY id DESC LIMIT 5", (bin_id,))
            logs = [dict(r) for r in cursor.fetchall()]

        current_level = bin_item["waste_level"]

        if current_level >= 100:
            est_hours = 0.0
            pred_text = "OVERFLOWING NOW"
        elif len(logs) < 2:
            fill_rate_per_hour = 3.5  # Default estimated slope %/hr
            remaining_pct = 100 - current_level
            est_hours = round(remaining_pct / fill_rate_per_hour, 1)
            pred_text = f"~{est_hours} hours to overflow"
        else:
            # Linear trend calculation
            recent = logs[0]["waste_level"]
            oldest = logs[-1]["waste_level"]
            delta = max(1, recent - oldest)
            est_rate_per_hr = max(2.0, delta * 1.5)
            remaining_pct = 100 - current_level
            est_hours = round(remaining_pct / est_rate_per_hr, 1)
            pred_text = f"~{est_hours} hours remaining"

        overflow_timestamp = (datetime.now() + timedelta(hours=est_hours)).strftime("%H:%M PM (%b %d)")

        predictions.append({
            "dustbin_id": bin_id,
            "location": bin_item["location"],
            "current_fill": current_level,
            "estimated_hours_to_full": est_hours,
            "predicted_overflow_time": overflow_timestamp,
            "prediction_text": pred_text
        })

    cursor.close()
    connection.close()

    return jsonify({"success": True, "predictions": predictions})


# Citizen Incident Reporting Endpoints
@app.route("/api/citizen-report", methods=["POST"])
def submit_citizen_report():
    data = request.get_json()
    if not data or not data.get("location_name") or not data.get("issue_type"):
        return jsonify({"success": False, "message": "Location and issue type are required"}), 400

    dustbin_id = data.get("dustbin_id")
    location_name = data.get("location_name").strip()
    issue_type = data.get("issue_type")
    description = data.get("description", "")
    reporter_name = data.get("reporter_name", "Anonymous Citizen")
    reporter_contact = data.get("reporter_contact", "")

    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            INSERT INTO citizen_reports (dustbin_id, location_name, issue_type, description, reporter_name, reporter_contact)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (dustbin_id, location_name, issue_type, description, reporter_name, reporter_contact))
    else:
        cursor.execute("""
            INSERT INTO citizen_reports (dustbin_id, location_name, issue_type, description, reporter_name, reporter_contact)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dustbin_id, location_name, issue_type, description, reporter_name, reporter_contact))

    connection.commit()
    report_id = cursor.lastrowid
    cursor.close()
    connection.close()

    return jsonify({"success": True, "message": "Thank you! Incident ticket reported successfully.", "report_id": report_id})


@app.route("/api/citizen-reports")
def get_citizen_reports():
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("SELECT * FROM citizen_reports ORDER BY id DESC LIMIT 30")
        reports = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM citizen_reports ORDER BY id DESC LIMIT 30")
        reports = [dict(r) for r in cursor.fetchall()]

    cursor.close()
    connection.close()

    return jsonify({"success": True, "reports": reports})


@app.route("/api/citizen-report/resolve/<int:report_id>", methods=["POST"])
def resolve_citizen_report(report_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("UPDATE citizen_reports SET status = 'Resolved' WHERE id = %s", (report_id,))
    else:
        cursor.execute("UPDATE citizen_reports SET status = 'Resolved' WHERE id = ?", (report_id,))

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"success": True, "message": f"Incident report #{report_id} marked as resolved."})


@app.route("/api/analytics")
def api_analytics():
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            SELECT t.dustbin_id, d.location, t.waste_level, t.recorded_at
            FROM telemetry_logs t
            LEFT JOIN dustbins d ON t.dustbin_id = d.id
            ORDER BY t.id DESC LIMIT 30
        """)
        logs = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) as total FROM collection_logs")
        col_count = cursor.fetchone()["total"]
    else:
        cursor.execute("""
            SELECT t.dustbin_id, d.location, t.waste_level, t.recorded_at
            FROM telemetry_logs t
            LEFT JOIN dustbins d ON t.dustbin_id = d.id
            ORDER BY t.id DESC LIMIT 30
        """)
        rows = cursor.fetchall()
        logs = [dict(r) for r in rows]
        cursor.execute("SELECT COUNT(*) FROM collection_logs")
        col_count = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    dustbins = get_waste_data()
    total_capacity = sum(b.get("capacity_liters", 120) for b in dustbins)
    current_volume = sum(b.get("capacity_liters", 120) * (b["waste_level"] / 100.0) for b in dustbins)
    avg_fill = round(sum(b["waste_level"] for b in dustbins) / max(len(dustbins), 1), 1)

    type_counts = {}
    for b in dustbins:
        btype = b.get("bin_type", "General Waste")
        type_counts[btype] = type_counts.get(btype, 0) + 1

    return jsonify({
        "success": True,
        "avg_fill_level": avg_fill,
        "total_capacity_liters": total_capacity,
        "current_volume_liters": round(current_volume, 1),
        "total_collections_made": col_count,
        "bin_type_distribution": type_counts,
        "recent_telemetry_logs": logs[::-1]
    })


@app.route("/api/export/csv")
def export_csv():
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            SELECT id, location, latitude, longitude, bin_type, capacity_liters,
                   waste_level, status, collection_status, battery_level, signal_rssi, last_updated
            FROM dustbins ORDER BY id ASC
        """)
        dustbins = cursor.fetchall()
        cursor.execute("SELECT * FROM collection_logs ORDER BY id DESC LIMIT 50")
        collections = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT id, location, latitude, longitude, bin_type, capacity_liters,
                   waste_level, status, collection_status, battery_level, signal_rssi, last_updated
            FROM dustbins ORDER BY id ASC
        """)
        dustbins = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM collection_logs ORDER BY id DESC LIMIT 50")
        collections = [dict(r) for r in cursor.fetchall()]

    cursor.close()
    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== SMART WASTE MANAGEMENT SYSTEM TELEMETRY REPORT ==="])
    writer.writerow([])
    writer.writerow(["ID", "Location", "Latitude", "Longitude", "Bin Type", "Capacity (L)", "Waste Level (%)", "Status", "Collection Status", "Battery (%)", "Signal (dBm)", "Last Updated"])

    for b in dustbins:
        writer.writerow([
            b.get("id"),
            b.get("location"),
            b.get("latitude"),
            b.get("longitude"),
            b.get("bin_type"),
            b.get("capacity_liters"),
            b.get("waste_level"),
            b.get("status"),
            b.get("collection_status"),
            b.get("battery_level"),
            b.get("signal_rssi"),
            b.get("last_updated")
        ])

    writer.writerow([])
    writer.writerow(["=== RECENT COLLECTION AUDIT LOGS ==="])
    writer.writerow(["Log ID", "Dustbin ID", "Location", "Waste Level Before Collection (%)", "Collected At"])

    for c in collections:
        writer.writerow([
            c.get("id"),
            c.get("dustbin_id"),
            c.get("location"),
            c.get("waste_level_before"),
            c.get("collected_at")
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=smart_waste_telemetry_report.csv"}
    )


@app.route("/api/simulate", methods=["POST"])
def simulate_telemetry():
    bins = get_waste_data()
    updated = []
    connection = get_db_connection()
    cursor = connection.cursor()

    for bin_item in bins:
        current = bin_item["waste_level"]
        if bin_item["collection_status"] == "Collected":
            new_level = random.randint(10, 35)
        else:
            delta = random.randint(5, 25)
            new_level = min(100, current + delta)

        new_status = get_status(new_level)
        bin_id = bin_item["id"]
        battery = max(15, bin_item.get("battery_level", 90) - random.choice([0, 0, 1]))

        if USE_MYSQL:
            cursor.execute("""
                UPDATE dustbins
                SET waste_level = %s,
                    status = %s,
                    battery_level = %s,
                    collection_status = %s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_level, new_status, battery, "Pending" if new_level > 30 else bin_item["collection_status"], bin_id))
            cursor.execute("""
                INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
                VALUES (%s, %s, %s)
            """, (bin_id, new_level, battery))
        else:
            cursor.execute("""
                UPDATE dustbins
                SET waste_level = ?,
                    status = ?,
                    battery_level = ?,
                    collection_status = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_level, new_status, battery, "Pending" if new_level > 30 else bin_item["collection_status"], bin_id))
            cursor.execute("""
                INSERT INTO telemetry_logs (dustbin_id, waste_level, battery_level)
                VALUES (?, ?, ?)
            """, (bin_id, new_level, battery))

        updated.append({
            "id": bin_id,
            "location": bin_item["location"],
            "waste_level": new_level,
            "status": new_status,
            "battery_level": battery
        })

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Simulated new IoT sensor readings",
        "dustbins": updated
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)