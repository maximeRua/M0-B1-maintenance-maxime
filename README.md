# FastIA - Service de criticité en maintenance prédictive (M0-B1)

API REST (FastAPI) qui expose un modèle scikit-learn pré-entraîné : à partir des
7 caractéristiques observables d'une machine industrielle, elle prédit sa
**criticité** (`basse`, `moyenne` ou `haute`) et renvoie les probabilités
associées

| Route | Rôle |
|---|---|
| `GET /health` | Santé du service et du modèle (`{"status": "ok", "model_loaded": true}`) |
| `POST /predict` | Prédiction de criticité : classe + probabilités |
| `POST /notes`, `GET /notes/{idx}` | Routes d'exemple issues du mini-cours FastAPI (stockage en mémoire, hors périmètre du service) |
| `GET /docs` | Documentation interactive Swagger (générée automatiquement) |

---

## Lancer le service en 5 minutes

**Prérequis :** Python 3.11+ (testé en 3.13) et `git`. Docker est nécessaire
uniquement pour la section [Docker](#-docker)

### 1. Récupérer le code et installer les dépendances

```bash
git clone https://github.com/maximeRua/M0-B1-maintenance-Maxime.git
cd M0-B1-maintenance-Maxime

# Linux / macOS
python -m venv .venv && source .venv/bin/activate
# Windows (PowerShell)
#   python -m venv .venv ; .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Démarrer l'API

```bash
uvicorn app.main:app --reload
```

L'API écoute sur <http://localhost:8000>. Le modèle (`model/model.joblib`, déjà
fourni) est chargé une seule fois au démarrage. Ouvre
<http://localhost:8000/docs> pour tester les routes depuis le navigateur.

### 3. Vérifier que ça répond

```bash
curl http://localhost:8000/health
# {"status":"ok","model_loaded":true}
```

> Le port 8000 est déjà pris ? Lance `uvicorn app.main:app --reload --port 8001`.

---

## Utiliser l'API

### `POST /predict`

**Corps de la requête** (JSON) - les 7 champs sont obligatoires :

| Champ | Type | Contrainte |
|---|---|---|
| `type_machine` | texte | `pompe`, `compresseur`, `convoyeur`, `presse` ou `four` |
| `age_machine_jours` | entier | 0 à 10 000 |
| `derniere_maintenance_jours` | entier | 0 à 365 |
| `temperature_moyenne` | nombre | °C (moyenne 7 derniers jours) |
| `vibration_moyenne` | nombre | ≥ 0, mm/s |
| `pression_moyenne` | nombre | ≥ 0, bar |
| `nb_incidents_3_mois` | entier | ≥ 0 |

**Exemple (curl, Linux/macOS/Git Bash) :**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"type_machine":"pompe","age_machine_jours":1200,"derniere_maintenance_jours":90,"temperature_moyenne":85.0,"vibration_moyenne":4.2,"pression_moyenne":6.5,"nb_incidents_3_mois":1}'
```

**Exemple (PowerShell) :**

```powershell
$body = @{
  type_machine = "pompe"; age_machine_jours = 1200; derniere_maintenance_jours = 90
  temperature_moyenne = 85.0; vibration_moyenne = 4.2; pression_moyenne = 6.5
  nb_incidents_3_mois = 1
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/predict -ContentType "application/json" -Body $body
```

**Réponse `200 OK` :**

```json
{
  "criticite": "moyenne",
  "probabilites": {"basse": 0.465, "haute": 0.045, "moyenne": 0.49}
}
```

**Codes d'erreur :**

| Code | Cause |
|---|---|
| `422` | Entrée invalide (champ manquant, type inconnu, valeur hors bornes) - le détail désigne le champ fautif |
| `503` | Modèle non chargé |
| `500` | Erreur pendant l'inférence (détails dans les logs) |

---

## Tests

```bash
pytest -v
```

13 tests : `/health` (2) et `/predict` (11 : cas valide, type de machine
invalide, champ manquant, 3 valeurs hors bornes, un test par type de machine).
Les tests n'ont pas besoin que le serveur tourne : `TestClient` simule les
requêtes en mémoire.

---

## Docker

```bash
docker build -t fastia-maintenance:dev .
docker run --rm -p 8000:8000 fastia-maintenance:dev
# dans un autre terminal :
curl http://localhost:8000/health
```

L'image (`python:3.11-slim`) embarque `app/` et `model/`. Le `.dockerignore`
exclut `.venv`, `tests`, `data`, etc. Un `HEALTHCHECK` interroge `/health` toutes
les 30 s (`docker ps` affiche `healthy` une fois le modèle chargé).

---

## Logs

Chaque requête `/predict` est tracée avec **Loguru** : entrée reçue, classe
prédite, probabilités et durée d'inférence en ms. Les logs vont dans la console
et dans `logs/api.log` (créé automatiquement, ignoré par git), avec rotation à
5 Mo, conservation 7 jours et compression zip.

```text
2026-11-24 09:26:18.610 | INFO     | app.main:predict:136 - Requête /predict reçue : {'type_machine': 'presse', 'age_machine_jours': 1500, ...}
2026-11-24 09:26:18.680 | INFO     | app.main:predict:154 - Prédiction = basse | probabilités = {'basse': 0.975, 'haute': 0.0, 'moyenne': 0.025} (durée 70.3 ms)
```

---

## Preuves de fonctionnement

Sorties réelles relevées le 24/11/2026.

**1. Tests - `pytest -v`**

```text
tests/test_health.py::test_health_returns_200 PASSED                     [  7%]
tests/test_health.py::test_health_response_schema PASSED                 [ 15%]
tests/test_predict.py::test_predict_cas_valide PASSED                    [ 23%]
tests/test_predict.py::test_predict_type_machine_invalide PASSED         [ 30%]
tests/test_predict.py::test_predict_champ_manquant PASSED                [ 38%]
tests/test_predict.py::test_predict_valeur_hors_bornes[age_machine_jours--1] PASSED [ 46%]
tests/test_predict.py::test_predict_valeur_hors_bornes[derniere_maintenance_jours-366] PASSED [ 53%]
tests/test_predict.py::test_predict_valeur_hors_bornes[vibration_moyenne--0.5] PASSED [ 61%]
tests/test_predict.py::test_predict_tous_types_machine[pompe] PASSED     [ 69%]
tests/test_predict.py::test_predict_tous_types_machine[compresseur] PASSED [ 76%]
tests/test_predict.py::test_predict_tous_types_machine[convoyeur] PASSED [ 84%]
tests/test_predict.py::test_predict_tous_types_machine[presse] PASSED    [ 92%]
tests/test_predict.py::test_predict_tous_types_machine[four] PASSED      [100%]

============================= 13 passed in 10.98s =============================
```

**2. Logging Loguru - fichier `logs/api.log` (livrable 4)**

Le fichier est créé automatiquement au premier lancement de l'API. Le dossier
`logs/` est ignoré par git (les logs ne se versionnent pas) : il n'apparaît donc
pas sur GitHub, mais il est généré dès qu'on lance l'API ou les tests.

```text
$ ls -l logs
-rw-r--r-- 1 mrua 1049089 8289 Nov 24 15:23 api.log

$ tail -n 5 logs/api.log
2026-11-24 15:23:51.719 | INFO     | app.main:predict:136 - Requête /predict reçue : {'type_machine': 'presse', 'age_machine_jours': 1500, 'derniere_maintenance_jours': 45, 'temperature_moyenne': 68.5, 'vibration_moyenne': 3.2, 'pression_moyenne': 7.8, 'nb_incidents_3_mois': 2}
2026-11-24 15:23:51.822 | INFO     | app.main:predict:154 - Prédiction = basse | probabilités = {'basse': 0.975, 'haute': 0.0, 'moyenne': 0.025} (durée 103.1 ms)
2026-11-24 15:23:51.827 | INFO     | app.main:predict:136 - Requête /predict reçue : {'type_machine': 'four', 'age_machine_jours': 1500, 'derniere_maintenance_jours': 45, 'temperature_moyenne': 68.5, 'vibration_moyenne': 3.2, 'pression_moyenne': 7.8, 'nb_incidents_3_mois': 2}
2026-11-24 15:23:51.925 | INFO     | app.main:predict:154 - Prédiction = basse | probabilités = {'basse': 0.96, 'haute': 0.0, 'moyenne': 0.04} (durée 98.0 ms)
2026-11-24 15:23:51.932 | INFO     | app.main:lifespan:80 - Service arrêté, état libéré.
```

**3. Docker - build de l'image (livrable 5)**

Extrait de la sortie : une ligne par étape, les détails de `pip install` sont omis.

```text
$ docker build --no-cache --progress=plain -t fastia-maintenance:dev .
#1 [internal] load build definition from Dockerfile
#2 [internal] load metadata for docker.io/library/python:3.11-slim
#3 [internal] load .dockerignore
#4 [internal] load build context
#5 [1/6] FROM docker.io/library/python:3.11-slim@sha256:61e01f72680f86a5279ad510818ab7b2ee9f049822589d4e34e33e044360356c
#6 [2/6] WORKDIR /app
#7 [3/6] COPY requirements.txt .
#8 [4/6] RUN pip install --no-cache-dir -r requirements.txt
#8 DONE 30.0s
#9 [5/6] COPY app/ ./app/
#10 [6/6] COPY model/ ./model/
#11 exporting to image
#11 naming to docker.io/library/fastia-maintenance:dev done
#11 DONE 17.8s
```

**4. Docker - run et `curl` depuis l'hôte (livrable 5)**

Le port 8000 de ma machine était déjà occupé par un autre conteneur : j'ai donc
publié le service sur le port **8001** de l'hôte (`-p 8001:8000`). Le service
écoute toujours sur le port 8000 *dans* le conteneur.

```text
$ docker run -d --rm --name fastia-proof -p 8001:8000 fastia-maintenance:dev

$ docker logs fastia-proof
INFO:     Started server process [1]
INFO:     Waiting for application startup.
2026-11-24 14:25:43.306 | INFO     | app.main:lifespan:72 - Chargement du modèle depuis /app/model/model.joblib
2026-11-24 14:25:44.441 | INFO     | app.main:lifespan:75 - Modèle chargé.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

$ curl http://localhost:8001/health
{"status":"ok","model_loaded":true}

$ curl -X POST http://localhost:8001/predict -H "Content-Type: application/json" -d '{"type_machine":"pompe","age_machine_jours":1200,"derniere_maintenance_jours":90,"temperature_moyenne":85.0,"vibration_moyenne":4.2,"pression_moyenne":6.5,"nb_incidents_3_mois":1}'
{"criticite":"moyenne","probabilites":{"basse":0.465,"haute":0.045,"moyenne":0.49}}

$ docker logs fastia-proof   # lignes ajoutées par la requête /predict
2026-11-24 14:25:46.478 | INFO     | app.main:predict:136 - Requête /predict reçue : {'type_machine': 'pompe', 'age_machine_jours': 1200, 'derniere_maintenance_jours': 90, [...]}
2026-11-24 14:25:46.582 | INFO     | app.main:predict:154 - Prédiction = moyenne | probabilités = {'basse': 0.465, 'haute': 0.045, 'moyenne': 0.49} (durée 103.5 ms)

$ docker ps --filter name=fastia-proof
NAMES          IMAGE                    PORTS                                         STATUS
fastia-proof   fastia-maintenance:dev   0.0.0.0:8001->8000/tcp, [::]:8001->8000/tcp   Up 8 seconds (healthy)
```

**5. Docker - image construite**

```text
$ docker images fastia-maintenance:dev
IMAGE                    ID             DISK USAGE   CONTENT SIZE
fastia-maintenance:dev   d8cf638d976d        775MB          176MB
```

## Régénérer dataset / modèle (optionnel)

Le dataset et le modèle sont déjà fournis. Pour les régénérer (déterministe,
`random_state=42`) :

```bash
python data/generate_dataset.py     # régénère le CSV
python model/train_baseline.py      # réentraîne le modèle (~30 s)
```

> `scikit-learn` doit rester à la version qui a produit `model.joblib`
> (cf. `requirements.txt`) ; en cas de changement de version, réentraîne.


## Erreurs rencontrés durant le brief

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError` au lancement | env virtuel pas activé / deps absentes | activer `.venv` puis `pip install -r requirements.txt` |
| `Modèle introuvable` au démarrage | `model.joblib` absent ou mal placé | `python model/train_baseline.py` |
| `/health` répond `degraded`, `/predict` répond 503 | modèle non chargé | vérifier les logs de démarrage |
| `pytest` échoue au clone | env virtuel inactif ou deps absentes | idem ligne 1 |
| Port 8000 déjà utilisé | un autre service tourne dessus | `uvicorn app.main:app --reload --port 8001` (.Net dans mon cas) |
| `curl: Connection refused` avec Docker | `-p 8000:8000` oublié au `docker run` | relancer avec le mapping de port |
