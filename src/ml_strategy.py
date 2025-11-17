import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential, load_model
import tensorflow as tf
tf.config.set_visible_devices([], 'GPU')
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from src.indicators import get_indicators
import joblib
import os

# Global variables for scaler and model
scaler = None
model = None
SEQUENCE_LENGTH = 60 # Number of past data points to consider for prediction
MODEL_PATH = 'ml_model.h5'
SCALER_PATH = 'scaler.pkl'
model_load_attempted = False

def create_sequences(data, sequence_length):
    """Create sequences from data for LSTM input."""
    xs, ys = [], []
    # Exclude 'target' column from features for X
    feature_columns = [col for col in data.columns if col != 'target']
    
    for i in range(len(data) - sequence_length):
        x = data.iloc[i:(i + sequence_length)][feature_columns].values
        y = data.iloc[i + sequence_length]['target'] # Assuming 'target' column exists
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def prepare_data_for_ml(historical_data):
    """
    Prepares historical data for ML model training/prediction.
    Includes feature engineering and scaling.
    """
    global scaler

    # Ensure necessary columns are present
    required_columns = ['open', 'high', 'low', 'close']
    for col in required_columns:
        if col not in historical_data.columns:
            # Fill missing required columns with zeros or appropriate defaults
            historical_data[col] = 0.0 # Or some other sensible default

    # Calculate indicators
    data = get_indicators(historical_data.copy())

    # Drop rows with NaN values that might result from indicator calculations
    data = data.dropna()

    if data.empty:
        return None, None

    # Define features (X) and target (y)
    # Target: 1 if next close price is higher, 0 otherwise
    data['target'] = (data['close'].shift(-1) > data['close']).astype(int)
    data = data.dropna() # Drop the last row where target is NaN

    if data.empty:
        return None, None

    features = [col for col in data.columns if col not in ['epoch', 'target', 'symbol']]
    
    if scaler is None:
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(data[features])

    scaled_data = scaler.transform(data[features])
    scaled_df = pd.DataFrame(scaled_data, columns=features, index=data.index)
    scaled_df['target'] = data['target']

    return scaled_df, features

def train_model():
    """
    Trains an LSTM model using historical data from historical_data.csv.
    """
    global model, scaler

    try:
        historical_data = pd.read_csv("historical_data.csv")
    except FileNotFoundError:
        print("historical_data.csv not found. Please run data_collector.py first.")
        return

    processed_data, features = prepare_data_for_ml(historical_data)
    if processed_data is None or processed_data.empty:
        print("Insufficient data to train the ML model.")
        return

    X, y = create_sequences(processed_data, SEQUENCE_LENGTH)

    if len(X) == 0:
        print("Not enough sequences to train the ML model.")
        return

    # Reshape X for LSTM input (samples, timesteps, features)
    X = X.reshape(X.shape[0], SEQUENCE_LENGTH, len(features))

    # Build LSTM model
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(1, activation='sigmoid') # Binary classification (up/down)
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

    # Train the model
    early_stopping = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
    
    # Simple train-validation split
    train_size = int(len(X) * 0.8)
    X_train, X_val = X[:train_size], X[train_size:]
    y_train, y_val = y[:train_size], y[train_size:]

    if len(X_train) == 0 or len(X_val) == 0:
        print("Not enough data for train-validation split. Skipping ML model training.")
        return

    print("Training ML model...")
    model.fit(X_train, y_train, epochs=50, batch_size=32, validation_data=(X_val, y_val), callbacks=[early_stopping], verbose=0)
    print("ML model training complete.")

    # Save the model and scaler
    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Model saved to {MODEL_PATH} and scaler to {SCALER_PATH}")

def load_model_and_scaler():
    """Loads the trained model and scaler from files."""
    global model, scaler, model_load_attempted
    model_load_attempted = True
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        model = load_model(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        print("ML model and scaler loaded.")
    else:
        print("ML model or scaler not found. Please train the model first.")

def predict_signal(current_data):
    """
    Uses the trained ML model to predict the next price movement.
    Returns 'buy', 'sell', or 'hold' and a confidence score.
    """
    global model, scaler, model_load_attempted

    if model is None or scaler is None:
        if not model_load_attempted:
            load_model_and_scaler()
        if model is None or scaler is None:
            return "hold", 0.0

    # Prepare current data for prediction
    # Ensure current_data has enough history for SEQUENCE_LENGTH
    if len(current_data) < SEQUENCE_LENGTH:
        print(f"Not enough data for ML prediction. Need {SEQUENCE_LENGTH} data points, got {len(current_data)}.")
        return "hold", 0.0

    # Take the last SEQUENCE_LENGTH data points
    data_for_prediction = current_data.iloc[-SEQUENCE_LENGTH:]

    # Calculate indicators for the prediction data
    data_for_prediction = get_indicators(data_for_prediction.copy())
    data_for_prediction = data_for_prediction.dropna()

    if data_for_prediction.empty or len(data_for_prediction) < SEQUENCE_LENGTH:
        print("Insufficient processed data for ML prediction.")
        return "hold", 0.0

    # Features should be consistent with training
    if scaler is not None and hasattr(scaler, 'feature_names_in_'):
        features = list(scaler.feature_names_in_)
    else:
        features = [col for col in data_for_prediction.columns if col not in ['epoch', 'symbol']]
    
    # Ensure the features used for prediction are the same as those used for training
    # This is a basic check, more robust handling might be needed
    if not all(f in data_for_prediction.columns for f in features):
        print("Mismatch in features for ML prediction. Skipping.")
        return "hold", 0.0

    scaled_data = scaler.transform(data_for_prediction[features])
    
    # Reshape for LSTM input
    X_pred = scaled_data.reshape(1, SEQUENCE_LENGTH, len(features))

    prediction_proba = model.predict(X_pred, verbose=0)[0][0]

    # Convert probability to signal
    if prediction_proba > 0.6: # High probability of going up
        return "buy", prediction_proba
    elif prediction_proba < 0.4: # High probability of going down
        return "sell", 1 - prediction_proba # Confidence for sell signal
    else:
        return "hold", 0.0 # Neutral, low confidence
