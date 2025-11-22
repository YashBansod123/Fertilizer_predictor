# 🌿 Smart Fertilizer System Dashboard

A blockchain-inspired data logging and fertilizer prediction system using:

✅ Flask (Backend API + Web Server)
✅ MongoDB (Data Storage)
✅ Machine Learning (Fertilizer Prediction)
✅ JSON Dataset Upload
✅ UAV Authentication System
✅ Blockchain-style Ledger

This project allows users to:

* Register UAV nodes
* Upload agricultural sensor datasets (JSON)
* Automatically store them in MongoDB
* Generate blockchain-like blocks for uploaded files
* Predict fertilizers using a trained ML model
* Retrieve uploaded datasets by UAV ID

---

# ✅ 1. Requirements

## ✅ Software Needed

Install these first:

* Python 3.12 ✅ (IMPORTANT — other versions may break ML)
* MongoDB Community Server
* MongoDB Compass (optional, GUI)
* Git

---

# ✅ 2. Clone the Repository

Open terminal / PowerShell:

```bash
git clone  https://github.com/YashBansod123/Fertilizer_predictor.git
cd YOUR_REPO
```

---

# ✅ 3. Create Virtual Environment (VERY IMPORTANT)

```bash
py -3.12 -m venv venv
```

Activate:

### Windows PowerShell

```bash
venv\Scripts\activate
```

---

# ✅ 4. Install Dependencies

```bash
pip install flask pymongo pandas joblib pycryptodome scikit-learn==1.3.2
```

✅ scikit-learn 1.3.2 is required — newer versions will break

---

# ✅ 5. Start MongoDB

### Windows

MongoDB starts automatically after installation

If not:

```bash
net start MongoDB
```

---

# ✅ 6. Run the Project

```bash
python app.py
```

You will see:

```
✅ ML model and label encoder loaded successfully!
Running on http://127.0.0.1:5000
```

Open:

```
http://127.0.0.1:5000
```

---

# ✅ 7. How to Use

## ✅ Step 1: Register UAV

Enter any ID (e.g., `1234`) → Click **Register UAV**

You will receive:

* UAV ID
* Token

## ✅ Step 2: Upload Dataset

Upload a `.json` file containing multiple crop records

Example format:

```json
[
  {"Temparature": 26, "Humidity": 60, "Moisture": 30, "Soil Type": "Sandy", "Crop Type": "Maize", "Nitrogen": 40, "Phosphorous": 20, "Potassium": 10}
]
```

After upload:
✅ File stored in MongoDB
✅ Blockchain block created

## ✅ Step 3: Predict Fertilizer

Click **Predict Fertilizer**

Outputs something like:

```
Maize → 20-20
Sugarcane → 17-17-17
```

## ✅ Step 4: Retrieve Dataset by UAV ID

Enter UAV ID → Click **Get Dataset**

Returns uploaded JSON

---

# ✅ 8. Model Retraining (Optional)

If you want to rebuild the ML model:

```bash
python model_train.py
```

This generates:

* `fertilizer_pipeline.pkl`
* `label_encoder.pkl`

---

# ✅ 9. Troubleshooting

### ✅ "monotonic_cst" error

Cause: scikit-learn version too new

Fix:

```
pip install scikit-learn==1.3.2
```

---

### ✅ No blocks in ledger

Cause: uploaded file was not `.json`

---

# ✅ 10. Folder Structure

```
project/
│ app.py
│ model_train.py
│ fertilizer_pipeline.pkl
│ label_encoder.pkl
│ uploads/
│ static/
│   script.js
│ templates/
│   index.html
```

---

# ✅ 11. Credits

Developer: Yash
Support: ChatGPT 😉

---

# ✅ 12. License

Free for educational use 🚀

---

If you want, I can:
✅ Add screenshots
✅ Add deployment guide (Render / Railway / AWS)
✅ Add blockchain verification feature

Just tell me 😎
