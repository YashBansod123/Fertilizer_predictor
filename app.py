from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import json
import uuid
import joblib
import pandas as pd
import warnings
from pymongo import MongoClient
from Crypto.Hash import SHA256   # ✅ NIST FIPS 180-4 compliant SHA-256
warnings.filterwarnings("ignore", category=UserWarning)

# --- MongoDB Configuration ---
MONGO_URI = "mongodb://localhost:27017/"  # change if using MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client["fertilizer_db"]
uav_collection = db["uavs"]
file_collection = db["uploaded_files"]

# --- Flask Configuration ---
app = Flask(__name__, static_folder='static', template_folder='templates')
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'csv', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- In-memory cache (optional) ---
registered_uavs = {}
data_blocks = []

# --- Load ML Model and Label Encoder ---
try:
    model_pipeline = joblib.load('fertilizer_pipeline.pkl')
    label_encoder = joblib.load('label_encoder.pkl')
    print("✅ ML model and label encoder loaded successfully!")
except FileNotFoundError:
    print("⚠️ Model files not found. Prediction endpoint will not work.")
    model_pipeline = None
    label_encoder = None


# --- Helper: NIST Hash (FIPS-180-4 compliant SHA-256) ---
def nist_hash(data_to_hash):
    """
    Generate a NIST FIPS-180-4 compliant SHA-256 hash using PyCryptodome.
    """
    if not isinstance(data_to_hash, bytes):
        data_to_hash = str(data_to_hash).encode('utf-8')
    hash_obj = SHA256.new(data_to_hash)
    return hash_obj.hexdigest()


# --- Helper: allowed file check ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Frontend Route ---
@app.route('/')
def index():
    return render_template('index.html')


# --- Register UAV ---
@app.route('/register_uav', methods=['POST'])
def register_uav():
    uav_id = request.json.get('uav_id')
    if not uav_id:
        return jsonify({"status": "error", "message": "UAV ID is required."}), 400

    existing_uav = uav_collection.find_one({"uav_id": uav_id})
    if existing_uav:
        return jsonify({"status": "error", "message": f"UAV '{uav_id}' is already registered."}), 409

    token = str(uuid.uuid4())
    uav_data = {"uav_id": uav_id, "token": token}
    uav_collection.insert_one(uav_data)

    return jsonify({
        "status": "success",
        "message": f"UAV '{uav_id}' registered successfully.",
        "uav_id": uav_id,
        "token": token
    }), 201


# --- Upload Dataset ---
@app.route('/upload_dataset', methods=['POST'])
def upload_dataset():
    uav_id = request.form.get('uav_id')
    token = request.form.get('token')

    # Authenticate UAV
    uav = uav_collection.find_one({"uav_id": uav_id, "token": token})
    if not uav:
        return jsonify({"status": "error", "message": "Authentication failed."}), 401

    if 'dataset' not in request.files:
        return jsonify({"status": "error", "message": "No file part in the request."}), 400

    file = request.files['dataset']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected."}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Compute NIST hash
        with open(filepath, 'rb') as f:
            file_content = f.read()
            file_hash = nist_hash(file_content)

        # Load JSON content
        with open(filepath, 'r') as f:
            json_data = json.load(f)

        new_block = {
            "block_id": len(data_blocks) + 1,
            "uploader_uav": uav_id,
            "filename": filename,
            "file_hash": file_hash,
            "size_bytes": len(file_content)
        }
        data_blocks.append(new_block)

        # Store file metadata + content in MongoDB
        file_record = {
            "uav_id": uav_id,
            "filename": filename,
            "file_hash": file_hash,
            "size_bytes": len(file_content),
            "data": json_data
        }
        file_collection.insert_one(file_record)

        return jsonify({
            "status": "success",
            "message": f"File '{filename}' uploaded and block generated.",
            "block_data": new_block
        }), 200

    return jsonify({"status": "error", "message": "File type not allowed."}), 400


# --- Get Uploaded Data (from MongoDB) ---
@app.route('/get_uploaded_data', methods=['GET'])
def get_uploaded_data():
    all_files = list(file_collection.find({}, {"_id": 0}))
    return jsonify(all_files)

def normalize_input_keys(data):
    """
    Fix key names from uploaded JSON so they match model training columns.
    """
    key_map = {
        "Temperature": "Temparature",  # ✅ convert to match model
    "temperature": "Temparature",
        "humidity": "Humidity",
        "moisture": "Moisture",
        "soil type": "Soil Type",
        "crop type": "Crop Type",
        "nitrogen": "Nitrogen",
        "potassium": "Potassium",
        "phosphorous": "Phosphorous"
    }

    normalized = {}
    for key, value in data.items():
        clean_key = key.strip()
        if clean_key in key_map:
            normalized[key_map[clean_key]] = value
        else:
            normalized[clean_key] = value
    return normalized

@app.route('/predict_fertilizer', methods=['POST'])
def predict_fertilizer():
    if model_pipeline is None or label_encoder is None:
        return jsonify({"status": "error", "message": "Model not loaded."}), 500

    input_data = request.json
    try:
        # Normalize key names
        normalized_input = normalize_input_keys(input_data)

        # Build dataframe and try to match model input
        features_df = pd.DataFrame([normalized_input])
        features_df = features_df.apply(pd.to_numeric, errors='ignore')

        print("\n===== DEBUG INFO =====")
        print("Incoming normalized keys:", normalized_input.keys())
        print("DataFrame columns:", features_df.columns.tolist())
        if hasattr(model_pipeline, 'feature_names_in_'):
            print("Model expects:", list(model_pipeline.feature_names_in_))
        print("Input record:", features_df.to_dict(orient='records'))
        print("=======================\n")

        prediction_encoded = model_pipeline.predict(features_df)
        prediction_name = label_encoder.inverse_transform(prediction_encoded)

        return jsonify({
            "status": "success",
            "predicted_fertilizer": prediction_name[0]
        })

    except Exception as e:
        import traceback
        print("\n⚠️ PREDICTION ERROR")
        traceback.print_exc()  # This will show the real cause
        print("======================\n")
        return jsonify({
            "status": "error",
            "message": f"{type(e).__name__}: {str(e)}"
        }), 400





# --- Ledger Endpoint (in-memory view) ---
@app.route('/get_ledger', methods=['GET'])
def get_ledger():
    return jsonify(data_blocks)


# --- Main ---
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True, port=5000)
