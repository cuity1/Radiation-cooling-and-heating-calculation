from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, runner


def test_default_config_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/default-config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["material"]["preset"] == "TiO2"
    assert payload["geometry"]["type"] == "sphere"
    assert payload["scan"]["wavelength_points"] == 160
    assert payload["scan"]["diameter_points"] == 80
    assert "particle" not in payload["material"]
    assert "validation" not in payload


def test_result_filename_rejects_path_traversal(tmp_path: Path) -> None:
    assert runner.result_file("../../bad", "config.json") is None


def test_auto_ellipsoid_queues_without_meep_guardrail(monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: object())
    client = TestClient(app)
    response = client.post("/api/simulations", json={"geometry": {"type": "ellipsoid"}, "scan": {"wavelength_points": 30, "diameter_points": 10}})
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] in {"queued", "running", "completed"}
