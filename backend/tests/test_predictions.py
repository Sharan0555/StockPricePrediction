from app.main import create_app
from fastapi.testclient import TestClient


def test_predictions_rejects_empty_closes() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/predictions",
            json={"symbol": "AAPL", "closes": []},
        )

    assert response.status_code == 422


def test_predictions_handles_value_error() -> None:
    app = create_app()

    def _raise_value_error(_: list[float]) -> dict:
        raise ValueError("closes must contain at least one price")

    from app.ml import inference

    original_predict = inference.prediction_engine.predict_next_price
    inference.prediction_engine.predict_next_price = _raise_value_error  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/predictions",
                json={"symbol": "AAPL", "closes": [123.0]},
            )
    finally:
        inference.prediction_engine.predict_next_price = original_predict

    assert response.status_code == 400
    assert response.json()["detail"] == "closes must contain at least one price"
