from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

CLASSES = {"basse", "moyenne", "haute"}
TYPES_MACHINE = ["pompe", "compresseur", "convoyeur", "presse", "four"]

def make_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type_machine": "compresseur",
        "age_machine_jours": 1500,
        "derniere_maintenance_jours": 45,
        "temperature_moyenne": 68.5,
        "vibration_moyenne": 3.2,
        "pression_moyenne": 7.8,
        "nb_incidents_3_mois": 2,
    }
    payload.update(overrides)
    return payload


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_predict_cas_valide(client: TestClient) -> None:
    r = client.post("/predict", json=make_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["criticite"] in CLASSES
    assert set(body["probabilites"].keys()) == CLASSES
    assert abs(sum(body["probabilites"].values()) - 1.0) < 1e-9
    meilleure = max(body["probabilites"], key=body["probabilites"].get)
    assert body["criticite"] == meilleure


def test_predict_type_machine_invalide(client: TestClient) -> None:
    r = client.post("/predict", json=make_payload(type_machine="INCONNU"))
    assert r.status_code == 422


def test_predict_champ_manquant(client: TestClient) -> None:
    payload = make_payload()
    del payload["vibration_moyenne"]
    r = client.post("/predict", json=payload)
    assert r.status_code == 422
    champs_en_erreur = [err["loc"][-1] for err in r.json()["detail"]]
    assert "vibration_moyenne" in champs_en_erreur


@pytest.mark.parametrize(
    "champ,valeur",
    [
        ("age_machine_jours", -1),
        ("derniere_maintenance_jours", 366),
        ("vibration_moyenne", -0.5),
    ],
)
def test_predict_valeur_hors_bornes(client: TestClient, champ: str, valeur: float) -> None:
    r = client.post("/predict", json=make_payload(**{champ: valeur}))
    assert r.status_code == 422


@pytest.mark.parametrize("type_m", TYPES_MACHINE)
def test_predict_tous_types_machine(client: TestClient, type_m: str) -> None:
    r = client.post("/predict", json=make_payload(type_machine=type_m))
    assert r.status_code == 200
    assert r.json()["criticite"] in CLASSES
