"""
Simple ZenML pipeline with sklearn and pandas
"""

import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from zenml import pipeline, step
from typing import Tuple, Annotated


@step
def load_data() -> Tuple[pd.DataFrame, pd.Series]:
    """Load the Iris dataset and return as pandas DataFrame and Series."""
    # Load iris dataset
    iris = load_iris()
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(iris.data, columns=iris.feature_names)
    target = pd.Series(iris.target, name='target')
    
    print(f"Loaded dataset with shape: {df.shape}")
    print(f"Features: {list(df.columns)}")
    print(f"Target classes: {len(target.unique())}")
    
    return df, target


@step
def split_data(
    df: pd.DataFrame, 
    target: pd.Series
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split data into training and testing sets."""
    X_train, X_test, y_train, y_test = train_test_split(
        df, target, test_size=0.2, random_state=42, stratify=target
    )
    
    print(f"Training set size: {len(X_train)}")
    print(f"Testing set size: {len(X_test)}")
    
    return X_train, X_test, y_train, y_test


@step
def train_model(
    X_train: pd.DataFrame, 
    y_train: pd.Series
) -> Annotated[LogisticRegression, "trained_model"]:
    """Train a logistic regression model."""
    model = LogisticRegression(random_state=42)
    model.fit(X_train, y_train)
    
    print("Model training completed")
    print(f"Model coefficients shape: {model.coef_.shape}")
    
    return model


@step
def evaluate_model(
    model: LogisticRegression,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> Annotated[float, "test_accuracy"]:
    """Evaluate the trained model and return test accuracy."""
    # Make predictions
    y_pred = model.predict(X_test)
    
    # Calculate accuracy
    accuracy = accuracy_score(y_test, y_pred)
    
    # Print detailed results
    print(f"Test Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    return accuracy


@pipeline(name="simple_sklearn_pipeline")
def simple_pipeline():
    """Simple ZenML pipeline with sklearn and pandas."""
    # Load data
    df, target = load_data()
    
    # Split data
    X_train, X_test, y_train, y_test = split_data(df, target)
    
    # Train model
    model = train_model(X_train, y_train)
    
    # Evaluate model
    accuracy = evaluate_model(model, X_test, y_test)
    
    return accuracy


if __name__ == "__main__":
    simple_pipeline()
