import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib

# --- START TRAINING ---
print("🌱 Starting Fertilizer Model Training...")

# ✅ Load dataset
df = pd.read_csv("DATASET-TRAIN.csv")

# ✅ Clean dataset
df = df.drop_duplicates()
df = df.dropna()  # remove missing rows to avoid training issues

print(f"✅ Loaded dataset with {len(df)} records.")

# ✅ Define input (X) and output (y)
X = df.drop(columns=["Fertilizer Name"])
y = df["Fertilizer Name"]

# ✅ Label encode target
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

# ✅ Define categorical and numeric columns
cat_cols = ["Soil Type", "Crop Type"]
num_cols = ["Temparature", "Humidity", "Moisture", "Nitrogen", "Potassium", "Phosphorous"]

# ✅ Build preprocessing pipeline
preprocessor = ColumnTransformer([
    ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
    ("num", StandardScaler(), num_cols)
])

# ✅ Decision Tree model (simple, stable)
model = DecisionTreeClassifier(random_state=42, max_depth=8)

# ✅ Build full ML pipeline
pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", model)
])

# ✅ Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
)

# ✅ Train the model
pipeline.fit(X_train, y_train)

# ✅ Evaluate accuracy
accuracy = pipeline.score(X_test, y_test)
print(f"✅ Model training complete! Accuracy: {accuracy * 100:.2f}%")

# ✅ Save model and encoder
joblib.dump(pipeline, "fertilizer_pipeline.pkl", compress=3)
joblib.dump(label_encoder, "label_encoder.pkl", compress=3)

print("💾 Model saved as 'fertilizer_pipeline.pkl' and 'label_encoder.pkl'")
print("🎉 Training process completed successfully!")
