import psycopg2
from flask import Flask, request, jsonify, redirect, render_template
import random
import string
import os
import logging
import validators
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Fix for psycopg2 requiring postgresql:// instead of postgres://
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://user:password@host:port/dbname")
DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Base URL for short links
BASE_URL = os.getenv("BASE_URL", "https://lutfil-url-tools.onrender.com/")


# Function to connect to PostgreSQL safely
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None


# Initialize the database (create table if not exists)
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id SERIAL PRIMARY KEY,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                clicks INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()


# Generate a unique short code
def generate_short_code():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        while True:
            short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            cursor.execute("SELECT short_code FROM urls WHERE short_code = %s", (short_code,))
            if not cursor.fetchone():  # Ensure it's unique
                break
        cursor.close()
        conn.close()
        return short_code
    return None


# Route for home page
@app.route('/')
def home():
    return render_template('index.html')


# Route to shorten a URL
@app.route('/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    original_url = data.get("original_url")

    if not original_url:
        return jsonify({"error": "Missing URL"}), 400

    # Ensure URL starts with http:// or https://
    if not original_url.startswith(('http://', 'https://')):
        original_url = "https://" + original_url

    # Validate the final URL
    if not validators.url(original_url):
        return jsonify({"error": "Invalid URL format"}), 400

    short_code = generate_short_code()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO urls (short_code, original_url, clicks) VALUES (%s, %s, 0)",
                   (short_code, original_url))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"short_url": f"{BASE_URL}/{short_code}"})


# Route to redirect to original URL
@app.route('/<short_code>')
def redirect_to_original(short_code):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT original_url FROM urls WHERE short_code = %s", (short_code,))
        result = cursor.fetchone()

        if result:
            cursor.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(result[0])

        cursor.close()
        conn.close()
    
    return jsonify({"error": "Short URL not found"}), 404


# Route to get URL click statistics
@app.route('/stats/<short_code>')
def get_click_stats(short_code):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT original_url, clicks FROM urls WHERE short_code = %s", (short_code,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            return jsonify({"original_url": result[0], "clicks": result[1]})

    return jsonify({"error": "Short URL not found"}), 404


# Run Flask app
if __name__ == '__main__':
    init_db()  # Ensure database is initialized
    app.run(debug=True)
