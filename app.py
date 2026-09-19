import os
import json
import sqlite3
import random
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

# Database Configuration (MySQL with automatic SQLite Fallback)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dustbins (
            id INTEGER PRIMARY KEY,
            location TEXT NOT NULL,
            waste_level INTEGER NOT NULL,
            status TEXT NOT NULL,
            collection_status TEXT NOT NULL DEFAULT 'Pending',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

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
                {"id": 1, "location": "Main Gate", "waste_level": 85},
                {"id": 2, "location": "Canteen", "waste_level": 70},
                {"id": 3, "location": "Library", "waste_level": 94}
            ]

        for bin_item in initial_bins:
            w_level = bin_item.get("waste_level", 0)
            status = get_status(w_level)
            cursor.execute("""
                INSERT INTO dustbins (id, location, waste_level, status, collection_status)
                VALUES (?, ?, ?, ?, 'Pending')
            """, (bin_item["id"], bin_item.get("location", f"Dustbin {bin_item['id']}"), w_level, status))
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
            SELECT id, location, waste_level, status,
            collection_status, last_updated
            FROM dustbins
            ORDER BY id ASC
        """)
        dustbins = cursor.fetchall()
        cursor.close()
        connection.close()
    else:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, location, waste_level, status,
            collection_status, last_updated
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


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    dustbins = get_waste_data()
    return render_template("dashboard.html", dustbins=dustbins)


@app.route("/collect/<int:dustbin_id>", methods=["POST"])
def collect_dustbin(dustbin_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            UPDATE dustbins
            SET collection_status = 'Collected',
                waste_level = 0,
                status = 'Normal',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
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

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "message": f"Dustbin {dustbin_id} marked as collected successfully!"
    })


@app.route("/api/dustbins")
def api_dustbins():
    dustbins = get_waste_data()
    return jsonify({
        "dustbins": dustbins
    })


@app.route("/api/update-dustbin", methods=["POST"])
def update_dustbin():
    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400

    dustbin_id = data.get("id")
    waste_level = data.get("waste_level")

    if dustbin_id is None or waste_level is None:
        return jsonify({
            "success": False,
            "message": "id and waste_level are required"
        }), 400

    try:
        dustbin_id = int(dustbin_id)
        waste_level = int(waste_level)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "id and waste_level must be numbers"
        }), 400

    if waste_level < 0 or waste_level > 100:
        return jsonify({
            "success": False,
            "message": "Waste level must be between 0 and 100"
        }), 400

    status = get_status(waste_level)

    connection = get_db_connection()
    cursor = connection.cursor()

    if USE_MYSQL:
        cursor.execute("""
            UPDATE dustbins
            SET waste_level = %s,
                status = %s,
                collection_status = 'Pending',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (waste_level, status, dustbin_id))
        connection.commit()
        rows_updated = cursor.rowcount
    else:
        cursor.execute("""
            UPDATE dustbins
            SET waste_level = ?,
                status = ?,
                collection_status = 'Pending',
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (waste_level, status, dustbin_id))
        connection.commit()
        rows_updated = cursor.rowcount

    cursor.close()
    connection.close()

    if rows_updated == 0:
        return jsonify({
            "success": False,
            "message": "Dustbin not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Dustbin data updated successfully",
        "dustbin_id": dustbin_id,
        "waste_level": waste_level,
        "status": status
    })


@app.route("/api/simulate", methods=["POST"])
def simulate_telemetry():
    bins = get_waste_data()
    updated = []
    connection = get_db_connection()
    cursor = connection.cursor()

    for bin_item in bins:
        new_level = random.randint(10, 98)
        new_status = get_status(new_level)
        bin_id = bin_item["id"]

        if USE_MYSQL:
            cursor.execute("""
                UPDATE dustbins
                SET waste_level = %s,
                    status = %s,
                    collection_status = 'Pending',
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_level, new_status, bin_id))
        else:
            cursor.execute("""
                UPDATE dustbins
                SET waste_level = ?,
                    status = ?,
                    collection_status = 'Pending',
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_level, new_status, bin_id))

        updated.append({
            "id": bin_id,
            "location": bin_item["location"],
            "waste_level": new_level,
            "status": new_status
        })

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Simulated new IoT ultrasonic sensor readings",
        "dustbins": updated
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)