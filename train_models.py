import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib

# Load historical project data
def load_historical_data():
    """Loads historical project effort and pricing data for model training."""
    return pd.read_csv("historical_project_pricing_data.csv")

# Train a model for effort estimation
def train_effort_estimation_model():
    """Trains a machine learning model to estimate resource effort based on project parameters."""
    df = load_historical_data()
    
    # Selecting relevant features
    X = df[['Project_Type', 'Complexity', 'Team_Size', 'Duration_Weeks']]
    y = df['Effort_Hours']
    
    # One-hot encoding for categorical variables
    X = pd.get_dummies(X, columns=['Project_Type', 'Complexity'], drop_first=True)

    # Splitting dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate model
    y_pred = model.predict(X_test)
    print("Effort Estimation MAE:", mean_absolute_error(y_test, y_pred))

    # Save model
    joblib.dump(model, "effort_model.pkl")

# Train a model for pricing prediction
def train_pricing_model():
    """Trains a machine learning model to predict project pricing based on effort and resource costs."""
    df = load_historical_data()
    
    # Selecting relevant features
    X = df[['Project_Type', 'Complexity', 'Effort_Hours', 'Resource_Cost_Per_Hour']]
    y = df['Total_Cost']
    
    # One-hot encoding for categorical variables
    X = pd.get_dummies(X, columns=['Project_Type', 'Complexity'], drop_first=True)

    # Splitting dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate model
    y_pred = model.predict(X_test)
    print("Pricing Estimation MAE:", mean_absolute_error(y_test, y_pred))

    # Save model
    joblib.dump(model, "pricing_model.pkl")

if __name__ == "__main__":
    train_effort_estimation_model()
    train_pricing_model()
