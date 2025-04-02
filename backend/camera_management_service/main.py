from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Tuple, Any  # Import typing hints

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_HOST = "localhost"
DB_NAME = "container_ocr"
DB_USER = "postgres"
DB_PASSWORD = "Man782761"  # Replace with your PostgreSQL password


def get_db_connection() -> psycopg2.extensions.connection:
    """Gets a database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.Error as e:
        logging.critical(f"Database connection error: {e}")
        raise  # Re-raise the exception to fail fast


def execute_query(query: str, params: Tuple = None, fetch: bool = False, fetchall: bool = False) -> Any:
    """Executes a database query with error handling."""

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if fetch:
            return cursor.fetchone()
        elif fetchall:
            return cursor.fetchall()
        else:
            conn.commit()
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Database query error: {e}, Query: {query}, Params: {params}")
        raise  # Re-raise to indicate failure
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/cameras', methods=['POST'])
def add_camera():
    """Adds a new camera."""

    data = request.get_json()
    ip_address = data.get("ip_address")
    location = data.get("location")

    if not ip_address or not location:
        return jsonify({"error": "ip_address and location are required"}), 400

    query = "INSERT INTO cameras (ip_address, location) VALUES (%s, %s) RETURNING id, ip_address, location"
    try:
        new_camera = execute_query(query, (ip_address, location), fetch=True)
        logging.info(f"Camera added: {new_camera}")
        return jsonify(
            {"id": new_camera[0], "ip_address": new_camera[1], "location": new_camera[2]}
        ), 201
    except psycopg2.Error:
        return jsonify({"error": "Failed to add camera"}), 500


@app.route('/cameras', methods=['GET'])
def get_cameras():
    """Gets all cameras."""

    query = "SELECT id, ip_address, location FROM cameras"
    try:
        cameras = execute_query(query, fetchall=True)
        logging.info("Cameras retrieved successfully")
        return jsonify(cameras)
    except psycopg2.Error:
        return jsonify({"error": "Failed to retrieve cameras"}), 500


@app.route('/cameras/<int:camera_id>', methods=['GET'])
def get_camera(camera_id: int):
    """Gets a specific camera by ID."""

    query = "SELECT id, ip_address, location FROM cameras WHERE id = %s"
    try:
        camera = execute_query(query, (camera_id,), fetch=True)
        if camera:
            logging.info(f"Camera {camera_id} retrieved successfully")
            return jsonify(camera)
        else:
            logging.warning(f"Camera {camera_id} not found")
            return jsonify({"message": "Camera not found"}), 404
    except psycopg2.Error:
        return jsonify({"error": f"Failed to retrieve camera {camera_id}"}), 500


@app.route('/cameras/<int:camera_id>', methods=['PUT'])
def update_camera(camera_id: int):
    """Updates a specific camera."""

    data = request.get_json()
    ip_address = data.get("ip_address")
    location = data.get("location")

    if not ip_address or not location:
        return jsonify({"error": "ip_address and location are required"}), 400

    query = "UPDATE cameras SET ip_address = %s, location = %s WHERE id = %s"
    try:
        execute_query(query, (ip_address, location, camera_id))
        logging.info(f"Camera {camera_id} updated successfully")
        return jsonify({"message": "Camera updated successfully"})
    except psycopg2.Error:
        return jsonify({"error": f"Failed to update camera {camera_id}"}), 500


@app.route('/cameras/<int:camera_id>', methods=['DELETE'])
def delete_camera(camera_id: int):
    """Deletes a specific camera."""

    query = "DELETE FROM cameras WHERE id = %s"
    try:
        execute_query(query, (camera_id,))
        logging.info(f"Camera {camera_id} deleted successfully")
        return jsonify({"message": "Camera deleted successfully"})
    except psycopg2.Error:
        return jsonify({"error": f"Failed to delete camera {camera_id}"}), 500


@app.route('/cameras/reset', methods=['DELETE'])
def reset_cameras():
    """Resets the camera list (deletes all cameras)."""

    query = "DELETE FROM cameras"
    try:
        execute_query(query)
        logging.info("Camera list reset successfully")
        return jsonify({"message": "Camera list reset successfully"}), 200
    except psycopg2.Error:
        return jsonify({"error": "Failed to reset camera list"}), 500


def initialize_db():
    """Initializes the database table."""

    query = """
        CREATE TABLE IF NOT EXISTS cameras (
            id SERIAL PRIMARY KEY,
            ip_address TEXT,
            location TEXT
        )
    """
    try:
        execute_query(query)
        logging.info("Cameras table created (if not exists)")
    except psycopg2.Error as e:
        logging.critical(f"Error creating cameras table: {e}")
        raise  # Re-raise to prevent app startup


if __name__ == '__main__':
    try:
        initialize_db()
        app.run(debug=True, port=5001)  # Specify the port here
    except psycopg2.Error:
        print("Database initialization failed. Application cannot start.")