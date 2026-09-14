from flask import Flask, render_template, jsonify, request
import mysql.connector

app = Flask(__name__)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="inventory@212427",
        database="smart_waste_db"
    )


def get_status(waste_level):
    if waste_level <= 50:
        return "Normal"
    elif waste_level <= 80:
        return "Warning"
    else:
        return "Full"


def get_waste_data():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, location, waste_level, status,
        collection_status, last_updated
        FROM dustbins
        """
    )

    dustbins = cursor.fetchall()

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

    return render_template(
        "dashboard.html",
        dustbins=dustbins
    )


@app.route("/collect/<int:dustbin_id>", methods=["POST"])
def collect_dustbin(dustbin_id):

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE dustbins
        SET collection_status = 'Collected',
            waste_level = 0,
            status = 'Normal',
            last_updated = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (dustbin_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return jsonify({
        "message": "Dustbin collected successfully"
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

    cursor.execute(
        """
        UPDATE dustbins
        SET waste_level = %s,
            status = %s,
            collection_status = 'Pending',
            last_updated = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (waste_level, status, dustbin_id)
    )

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


if __name__ == "__main__":
    app.run(debug=True)