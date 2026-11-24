"""API FastAPI — service de classification de criticité (M0-B1).

Expose un modèle scikit-learn pré-entraîné (cf. `model/train_baseline.py`) via
deux routes :

- `GET /health`  : santé du service
- `POST /predict` : prédiction de criticité (classe + probabilités)

Le modèle est chargé une seule fois au démarrage via le `lifespan` FastAPI puis
réutilisé pour chaque requête. Chaque prédiction est journalisée avec Loguru
(entrée, sortie, durée) dans la console et dans `logs/api.log`.

Lancement local :
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.schemas import HealthResponse, MachineInput, PredictionResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "model" / "model.joblib"
LOG_DIR = ROOT_DIR / "logs"

# Sink fichier (en plus de la console, active par défaut dans Loguru).
# `enqueue=True` : écriture thread-safe, indispensable sous uvicorn.
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "api.log",
    rotation="5 MB",
    retention="7 days",
    compression="zip",
    level="INFO",
    enqueue=True,
)


class Note(BaseModel):
    titre: str
    contenu: str


# Mémoire d'application — peuplée par le lifespan
state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle au démarrage, libère à l'arrêt.

    Args:
        app: instance FastAPI.
    """
    if not MODEL_PATH.is_file():
        logger.error(
            f"Modèle introuvable : {MODEL_PATH}. "
            f"Lance d'abord : python model/train_baseline.py"
        )
        raise RuntimeError(f"Modèle introuvable : {MODEL_PATH}")

    logger.info(f"Chargement du modèle depuis {MODEL_PATH}")
    state["model"] = joblib.load(MODEL_PATH)
    state["notes"] = []  # « base de données » en mémoire (routes /notes)
    logger.info("Modèle chargé.")

    yield

    state.clear()
    logger.info("Service arrêté, état libéré.")


app = FastAPI(
    title="FastIA — Service de criticité maintenance prédictive",
    description=(
        "API d'exposition d'un modèle scikit-learn de classification de criticité "
        "d'incidents machine (3 classes : basse, moyenne, haute)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Retourne le statut du service et du modèle.

    Returns:
        HealthResponse — `status="ok"` si le modèle est chargé, `degraded` sinon.
    """
    is_loaded = "model" in state
    return HealthResponse(
        status="ok" if is_loaded else "degraded",
        model_loaded=is_loaded,
    )


@app.post("/notes", response_model=Note, status_code=201)
def creer_note(note: Note) -> Note:
    state["notes"].append(note)
    return note


@app.get("/notes/{idx}", response_model=Note)
def lire_note(idx: int) -> Note:
    notes = state["notes"]
    if idx < 0 or idx >= len(notes):
        raise HTTPException(404, "Note introuvable")
    return notes[idx]


@app.post("/predict", response_model=PredictionResponse)
def predict(item: MachineInput) -> PredictionResponse:
    """Prédit la criticité d'une machine à partir de ses caractéristiques.

    Args:
        item: caractéristiques de la machine (cf. `schemas.MachineInput`).

    Returns:
        PredictionResponse avec la classe prédite et les probabilités.

    Raises:
        HTTPException: 503 si le modèle n'est pas chargé, 500 si l'inférence échoue.
    """
    payload = item.model_dump()
    logger.info("Requête /predict reçue : {}", payload)

    model = state.get("model")
    if model is None:
        logger.error("Requête /predict refusée : modèle non chargé.")
        raise HTTPException(status_code=503, detail="Modèle non chargé.")

    try:
        t0 = time.perf_counter()
        df = pd.DataFrame([payload])
        classe = str(model.predict(df)[0])
        probas = model.predict_proba(df)[0]
        duree_ms = (time.perf_counter() - t0) * 1000
    except Exception:
        logger.exception("Échec de l'inférence pour l'entrée : {}", payload)
        raise HTTPException(status_code=500, detail="Erreur lors de la prédiction.")

    probabilites = {str(nom): float(p) for nom, p in zip(model.classes_, probas)}
    logger.info(
        "Prédiction = {} | probabilités = {} (durée {:.1f} ms)",
        classe,
        {k: round(v, 3) for k, v in probabilites.items()},
        duree_ms,
    )
    return PredictionResponse(criticite=classe, probabilites=probabilites)
