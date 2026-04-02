import os
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
from datetime import datetime

from config import MODEL_PATH, RISK_DATA_PATH

print("=" * 60)
print("🚀 Safe Sprout: ML Model Training")
print("=" * 60)
print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
print()

# Step 1: Load Risk Grid Data
print("[1/6] Loading risk grid data...")
print("      " + "─" * 50)

if not os.path.exists(RISK_DATA_PATH):
    print(f"❌ Error: Risk grid not found at {RISK_DATA_PATH}")
    print("💡 Run assign_risk_scores.py first!")
    exit()

with open(RISK_DATA_PATH, 'r') as f:
    risk_data = json.load(f)

print(f"      ✅ Loaded {len(risk_data)} regions from risk grid")
print(f"      📁 File: {RISK_DATA_PATH}")
print()

# Step 2: Prepare Training Data
print("[2/6] Preparing training data...")
print("      " + "─" * 50)

X = []  # Features
y = []  # Labels (0 = safe, 1 = unsafe)

feature_names = [
    'latitude', 'longitude', 'hour_of_day', 'day_of_week',
    'crime_count_7d', 'crime_count_30d', 'night_crime_ratio',
    'lighting_score', 'foot_traffic', 'police_proximity', 'public_transport_access'
]

for i, point in enumerate(risk_data, 1):
    lat = point.get('Latitude', 0)
    lng = point.get('Longitude', 0)
    risk = point.get('risk', 0.5)
    
    # Get breakdown if available
    breakdown = point.get('breakdown', {})
    
    # Create realistic features based on risk score
    features = [
        lat,                                    # latitude
        lng,                                    # longitude
        np.random.randint(0, 24),              # hour_of_day
        np.random.randint(0, 7),               # day_of_week
        int(risk * 10 * 0.3),                  # crime_count_7d
        int(risk * 10),                        # crime_count_30d
        risk * 0.7 + 0.1,                      # night_crime_ratio
        10 - (risk * 8),                       # lighting_score (high risk = poor lighting)
        10 - (risk * 6),                       # foot_traffic (high risk = less traffic)
        1 + (risk * 4),                        # police_proximity (high risk = farther)
        0.5 + (risk * 1.5),                    # public_transport_access
    ]
    
    X.append(features)
    # Label: 1 if risk > 0.5 (unsafe), 0 if risk <= 0.5 (safe)
    y.append(1 if risk > 0.5 else 0)
    
    # Progress indicator
    progress = (i / len(risk_data)) * 100
    print(f"      📊 Processing region {i}/{len(risk_data)} ({progress:.0f}%)", end='\r')

X = np.array(X)
y = np.array(y)

print(f"      ✅ Feature matrix shape: {X.shape}")
print(f"      ✅ Class distribution: Safe={sum(y==0)}, Unsafe={sum(y==1)}")
print()

# Step 3: Split Data
print("[3/6] Splitting data (80% train, 20% test)...")
print("      " + "─" * 50)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"      ✅ Training samples: {len(X_train)}")
print(f"      ✅ Test samples: {len(X_test)}")
print()

# Step 4: Scale Features
print("[4/6] Scaling features...")
print("      " + "─" * 50)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"      ✅ Features scaled (mean=0, std=1)")
print()

# Step 5: Train Random Forest
print("[5/6] Training Random Forest classifier...")
print("      " + "─" * 50)

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=15,
    min_samples_split=5,
    min_samples_leaf=2,
    class_weight='balanced',
    random_state=42,
    n_jobs=-1,
    verbose=1
)

# Train with progress
print(f"      🌲 Training 200 decision trees...")
model.fit(X_train_scaled, y_train)

print(f"      ✅ Model training complete!")
print()

# Step 6: Evaluate Model
print("[6/6] Evaluating model performance...")
print("      " + "─" * 50)

y_pred = model.predict(X_test_scaled)

train_acc = model.score(X_train_scaled, y_train)
test_acc = accuracy_score(y_test, y_pred)
cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)
cv_mean = cv_scores.mean()

print(f"      ✅ Training accuracy: {train_acc:.2%}")
print(f"      ✅ Test accuracy: {test_acc:.2%}")
print(f"      ✅ Cross-validation (5-fold): {cv_mean:.2%}")
print()

print(f"      📋 Classification Report:")
print("      " + "─" * 50)
report = classification_report(y_test, y_pred, target_names=['Safe', 'Unsafe'], output_dict=True)
for class_name in ['Safe', 'Unsafe']:
    if class_name in report:
        precision = report[class_name]['precision']
        recall = report[class_name]['recall']
        f1 = report[class_name]['f1-score']
        print(f"      {class_name:8s}: Precision={precision:.2f}, Recall={recall:.2f}, F1={f1:.2f}")

print()
print(f"      🔍 Confusion Matrix:")
print("      " + "─" * 50)
cm = confusion_matrix(y_test, y_pred)
print(f"      [[{cm[0][0]:3d}  {cm[0][1]:3d}]  ← Predicted Safe")
print(f"       [{cm[1][0]:3d}  {cm[1][1]:3d}]] ← Predicted Unsafe")
print(f"        ↑ True Safe   ↑ True Unsafe")

print()
print(f"      🎯 Top 5 Most Important Features:")
print("      " + "─" * 50)
importances = model.feature_importances_
indices = np.argsort(importances)[::-1][:5]
for i, idx in enumerate(indices, 1):
    print(f"      {i}. {feature_names[idx]:25s}: {importances[idx]:.3f}")

print()

# Save Model and Scaler
print("=" * 60)
print("💾 Saving model and scaler...")
print("=" * 60)

os.makedirs('models', exist_ok=True)

model_path = MODEL_PATH
scaler_path = 'models/scaler.pkl'
metadata_path = 'models/model_metadata.json'

joblib.dump(model, model_path)
print(f"      ✅ Model saved to: {model_path}")

joblib.dump(scaler, scaler_path)
print(f"      ✅ Scaler saved to: {scaler_path}")

# Save metadata
metadata = {
    'feature_names': feature_names,
    'training_samples': len(X_train),
    'test_samples': len(X_test),
    'class_distribution': {
        'safe': int(sum(y_train==0)),
        'unsafe': int(sum(y_train==1))
    },
    'model_params': {
        'n_estimators': 200,
        'max_depth': 15,
        'min_samples_split': 5,
    },
    'performance': {
        'train_accuracy': round(train_acc, 4),
        'test_accuracy': round(test_acc, 4),
        'cv_mean': round(cv_mean, 4),
    },
    'trained_at': datetime.now().isoformat()
}

with open(metadata_path, 'w') as f:
    json.dump(metadata, f, indent=2)
print(f"      ✅ Metadata saved to: {metadata_path}")

print()
print("=" * 60)
print("🎉 TRAINING COMPLETE!")
print("=" * 60)
print(f"⏰ Finished at: {datetime.now().strftime('%H:%M:%S')}")
print()
print("📁 Files Created:")
print(f"   • {model_path}")
print(f"   • {scaler_path}")
print(f"   • {metadata_path}")
print()
print("🚀 Next Steps:")
print("   1. Restart backend: python main.py")
print("   2. Test prediction: curl -X POST http://localhost:8000/predict/risk ...")
print("   3. Run Flutter app: flutter run")
print("   4. Toggle heatmap in app! 🔥")
print("=" * 60)