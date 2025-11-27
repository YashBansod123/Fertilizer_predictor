from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import json
import uuid
import joblib
import pandas as pd
import warnings
from pymongo import MongoClient
from Crypto.Hash import SHA256

warnings.filterwarnings("ignore", category=UserWarning)

# =====================================
# 🔗 MongoDB Setup
# =====================================
MONGO_URI = "mongodb://localhost:27017/"
client = MongoClient(MONGO_URI)
db = client["fertilizer_db"]
uav_collection = db["uavs"]
file_collection = db["uploaded_files"]
polygon_collection = db["polygons"]

# =====================================
# 🌐 Flask App
# =====================================
app = Flask(__name__, static_folder='static', template_folder='templates')
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"csv", "json", "txt"}

data_blocks = []  # in-memory “blockchain” view

# =====================================
# 📦 Load ML Model
# =====================================
try:
    model_pipeline = joblib.load("fertilizer_pipeline.pkl")
    label_encoder = joblib.load("label_encoder.pkl")
    print("✅ ML Model Loaded")
except Exception as e:
    print("❌ Model NOT FOUND:", e)
    model_pipeline = None
    label_encoder = None


# =====================================
# 🔐 Helpers
# =====================================
def nist_hash(data):
    """NIST-style SHA-256 using PyCryptodome"""
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8")
    h = SHA256.new(data)
    return h.hexdigest()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def point_in_polygon(lat, lon, poly_lonlat):
    """
    Pure Python ray-casting PIP test.
    poly_lonlat is a list of (lon, lat) vertices.
    """
    x, y = lon, lat
    inside = False
    n = len(poly_lonlat)

    for i in range(n):
        x1, y1 = poly_lonlat[i]
        x2, y2 = poly_lonlat[(i + 1) % n]

        # Check if edge crosses horizontal ray at y
        if (y1 > y) != (y2 > y):
            slope = (y - y1) * (x2 - x1) / (y2 - y1 + 1e-12) + x1
            if slope > x:
                inside = not inside

    return inside


def normalize_input_keys(d):
    """
    Fix key names from uploaded JSON so they match model training columns.
    """
    mapping = {
        "Temperature": "Temparature",
        "temperature": "Temparature",
        "Temparature": "Temparature",
        "humidity": "Humidity",
        "Humidity": "Humidity",
        "moisture": "Moisture",
        "Moisture": "Moisture",
        "soil type": "Soil Type",
        "Soil Type": "Soil Type",
        "crop type": "Crop Type",
        "Crop Type": "Crop Type",
        "nitrogen": "Nitrogen",
        "Nitrogen": "Nitrogen",
        "potassium": "Potassium",
        "Potassium": "Potassium",
        "phosphorous": "Phosphorous",
        "Phosphorous": "Phosphorous",
    }

    fixed = {}
    for k, v in d.items():
        k2 = k.strip()
        fixed[mapping.get(k2, k2)] = v
    return fixed


# =====================================
# 🌍 ROUTES – PAGES
# =====================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/map")
def map_page():
    return render_template("map.html")


# =====================================
# 1️⃣ REGISTER UAV
# =====================================
@app.route("/register_uav", methods=["POST"])
def register_uav():
    uav_id = request.json.get("uav_id")

    if not uav_id:
        return jsonify({"status": "error", "message": "UAV ID required"}), 400

    if uav_collection.find_one({"uav_id": uav_id}):
        return jsonify({"status": "error", "message": "UAV already registered"}), 409

    token = str(uuid.uuid4())
    uav_collection.insert_one({"uav_id": uav_id, "token": token})

    return jsonify({"status": "success", "uav_id": uav_id, "token": token})


# =====================================
# 2️⃣ UPLOAD DATASET (CSV / JSON)
# =====================================
@app.route("/upload_dataset", methods=["POST"])
def upload_dataset():
    uav_id = request.form.get("uav_id")
    token = request.form.get("token")

    # Auth
    uav = uav_collection.find_one({"uav_id": uav_id, "token": token})
    if not uav:
        return jsonify({"status": "error", "message": "Authentication Failed"}), 401

    if "dataset" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    file = request.files["dataset"]
    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "File type not allowed"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    file.save(filepath)

    with open(filepath, "rb") as f:
        file_content = f.read()
        file_hash = nist_hash(file_content)

    # SAFE CSV / JSON PARSE
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(filepath)

        # If you want coordinates for map, keep Latitude/Longitude
        # They MUST be present for polygon querying
        if "Latitude" in df.columns and "Longitude" in df.columns:
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
            df = df.dropna(subset=["Latitude", "Longitude"])

        df = df.where(pd.notnull(df), None)
        json_data = df.to_dict(orient="records")
    else:
        with open(filepath, "r") as f:
            json_data = json.load(f)

    # Block for ledger (in-memory)
    block = {
        "block_id": len(data_blocks) + 1,
        "uploader_uav": uav_id,
        "filename": filename,
        "file_hash": file_hash,
        "size_bytes": len(file_content),
    }
    data_blocks.append(block)

    # Save to Mongo
    file_collection.insert_one({
        "uav_id": uav_id,
        "filename": filename,
        "file_hash": file_hash,
        "size_bytes": len(file_content),
        "data": json_data,
    })

    return jsonify({"status": "success", "message": "Uploaded successfully", "block": block})


# =====================================
# 3️⃣ GET ALL UPLOADED DATA (for prediction)
# =====================================
@app.route("/get_uploaded_data", methods=["GET"])
def get_uploaded_data():
    files = list(file_collection.find({}, {"_id": 0}))
    return jsonify(files)


# =====================================
# 4️⃣ GET DATASET BY UAV (for “Retrieve Dataset” UI)
# =====================================
@app.route("/get_dataset_by_uav", methods=["GET"])
def get_dataset_by_uav():
    uav_id = request.args.get("uav_id")
    if not uav_id:
        return jsonify({"status": "error", "message": "uav_id is required"}), 400

    recs = list(file_collection.find({"uav_id": uav_id}, {"_id": 0}))
    if not recs:
        return jsonify({"status": "error", "message": f"No dataset found for UAV {uav_id}"})

    return jsonify({
        "status": "success",
        "uav_id": uav_id,
        "uploaded_files": recs
    })


# =====================================
# 5️⃣ LEDGER VIEW
# =====================================
@app.route("/get_ledger", methods=["GET"])
def get_ledger():
    return jsonify(data_blocks)


# =====================================
# 6️⃣ STORE POLYGON (with name)
# =====================================
@app.route("/store_polygon", methods=["POST"])
def store_polygon():
    data = request.json or {}
    coords = data.get("coords")
    name = data.get("name", "Unnamed Polygon")

    if not coords:
        return jsonify({"status": "error", "message": "No coordinates"}), 400

    polygon_id = str(uuid.uuid4())

    polygon_collection.insert_one({
        "polygon_id": polygon_id,
        "name": name,
        "coords": coords      # [[lat, lon], ...]
    })

    return jsonify({
        "status": "success",
        "polygon_id": polygon_id,
        "name": name
    })


# =====================================
# 7️⃣ GET ALL SAVED POLYGONS (for left folder panel)
# =====================================
@app.route("/get_polygons", methods=["GET"])
def get_polygons():
    polys = list(polygon_collection.find({}, {"_id": 0}))
    return jsonify({"status": "success", "polygons": polys})


# =====================================
# 8️⃣ GET DRONES INSIDE A POLYGON
# =====================================
@app.route("/drones_in_polygon", methods=["GET"])
def drones_in_polygon():
    polygon_id = request.args.get("polygon_id")

    poly_doc = polygon_collection.find_one({"polygon_id": polygon_id}, {"_id": 0})
    if not poly_doc:
        return jsonify({"status": "error", "message": "Polygon not found"}), 404

    # stored as [ [lat, lon], ... ] → convert to (lon, lat)
    poly_latlon = poly_doc["coords"]
    poly_lonlat = [(lng, lat) for lat, lng in poly_latlon]

    all_files = list(file_collection.find({}, {"_id": 0}))

    inside = []

    for drone in all_files:
        for rec in drone.get("data", []):
            lat = rec.get("Latitude")
            lon = rec.get("Longitude")

            if lat is None or lon is None:
                continue

            if point_in_polygon(lat, lon, poly_lonlat):
                inside.append({
                    "uav_id": drone.get("uav_id"),
                    "lat": lat,
                    "lon": lon,
                    "data": rec
                })

    return jsonify({
        "status": "success",
        "count": len(inside),
        "polygon_id": polygon_id,
        "drones_inside": inside
    })


# =====================================
# 9️⃣ PREDICT FERTILIZER
# =====================================
@app.route("/predict_fertilizer", methods=["POST"])
def predict_fertilizer():
    if model_pipeline is None or label_encoder is None:
        return jsonify({"status": "error", "message": "Model Missing"}), 500

    try:
        payload = request.json or {}
        payload = normalize_input_keys(payload)
        df = pd.DataFrame([payload])
        pred = model_pipeline.predict(df)
        fert = label_encoder.inverse_transform(pred)[0]
        return jsonify({"status": "success", "predicted_fertilizer": fert})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# =====================================
# RUN SERVER
# =====================================
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    print("🚀 Server running at http://127.0.0.1:5000")
    app.run(debug=True)
