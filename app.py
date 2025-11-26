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

data_blocks = []

# =====================================
# 📦 Load ML Model
# =====================================
try:
    model_pipeline = joblib.load("fertilizer_pipeline.pkl")
    label_encoder = joblib.load("label_encoder.pkl")
    print("✅ ML Model Loaded")
except:
    print("❌ Model NOT FOUND")
    model_pipeline = None
    label_encoder = None

# =====================================
# 🔐 Helpers
# =====================================
def nist_hash(data):
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8")
    h = SHA256.new(data)
    return h.hexdigest()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------------------
# 🔥 PURE PYTHON POINT-IN-POLYGON
# ------------------------------------
def point_in_polygon(lat, lon, poly):
    x, y = lon, lat  # use lon=x, lat=y
    inside = False

    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]

        if y1 > y and y2 <= y or y2 > y and y1 <= y:
            slope = (y - y1) * (x2 - x1) / (y2 - y1 + 0.0000001) + x1
            if slope > x:
                inside = not inside

    return inside

# =====================================
# 🌍 ROUTES
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
# 2️⃣ UPLOAD DATASET
# =====================================
@app.route("/upload_dataset", methods=["POST"])
def upload_dataset():
    uav_id = request.form.get("uav_id")
    token = request.form.get("token")

    uav = uav_collection.find_one({"uav_id": uav_id, "token": token})
    if not uav:
        return jsonify({"status": "error", "message": "Authentication Failed"}), 401

    if "dataset" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    file = request.files["dataset"]
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    with open(filepath, "rb") as f:
        file_content = f.read()
        file_hash = nist_hash(file_content)

    # ---------------------------
    # SAFE CSV HANDLING
    # ---------------------------
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(filepath)

        if "Latitude" not in df.columns or "Longitude" not in df.columns:
            return jsonify({"status": "error", "message": "CSV must contain Latitude & Longitude"}), 400

        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

        df = df.dropna(subset=["Latitude", "Longitude"])
        df = df.where(pd.notnull(df), None)

        json_data = df.to_dict(orient="records")

    else:
        with open(filepath, "r") as f:
            json_data = json.load(f)

    # Save Blockchain Block
    block = {
        "block_id": len(data_blocks) + 1,
        "uploader_uav": uav_id,
        "filename": filename,
        "file_hash": file_hash,
        "size_bytes": len(file_content)
    }
    data_blocks.append(block)

    file_collection.insert_one({
        "uav_id": uav_id,
        "filename": filename,
        "file_hash": file_hash,
        "size_bytes": len(file_content),
        "data": json_data
    })

    return jsonify({"status": "success", "message": "Uploaded successfully", "block": block})


# =====================================
# 3️⃣ STORE POLYGON
# =====================================
@app.route("/store_polygon", methods=["POST"])
def store_polygon():
    coords = request.json.get("coords")
    if not coords:
        return jsonify({"status": "error", "message": "No coordinates"}), 400

    polygon_id = str(uuid.uuid4())

    polygon_collection.insert_one({
        "polygon_id": polygon_id,
        "coords": coords
    })

    return jsonify({"status": "success", "polygon_id": polygon_id})


# =====================================
# 4️⃣ GET DRONES INSIDE POLYGON
# =====================================
@app.route("/drones_in_polygon", methods=["GET"])
def drones_in_polygon():
    polygon_id = request.args.get("polygon_id")

    poly_doc = polygon_collection.find_one({"polygon_id": polygon_id})
    if not poly_doc:
        return jsonify({"status": "error", "message": "Polygon not found"}), 404

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
                    "uav_id": drone["uav_id"],
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
# 5️⃣ PREDICT FERTILIZER
# =====================================
@app.route("/predict_fertilizer", methods=["POST"])
def predict_fertilizer():
    if model_pipeline is None:
        return jsonify({"status": "error", "message": "Model Missing"}), 500

    df = pd.DataFrame([request.json])
    pred = model_pipeline.predict(df)
    fert = label_encoder.inverse_transform(pred)[0]

    return jsonify({"status": "success", "predicted_fertilizer": fert})


# =====================================
# RUN SERVER
# =====================================
if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    print("🚀 Server running at http://127.0.0.1:5000")
    app.run(debug=True)
