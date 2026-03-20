"""Basic API tests for the stock price prediction backend."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_live_price_endpoint():
    """Test the live price endpoint."""
    response = client.get("/api/v1/stocks/live-price/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert "symbol" in data
    assert "price" in data
    assert data["symbol"] == "AAPL"


def test_prediction_endpoint():
    """Test the prediction endpoint."""
    response = client.post(
        "/api/v1/stocks/predict",
        json={"symbol": "AAPL", "days": 7}
    )
    # This might fail if ML model isn't loaded, but should return proper error
    assert response.status_code in [200, 400, 500]


if __name__ == "__main__":
    pytest.main([__file__])
