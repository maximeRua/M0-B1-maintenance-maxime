# Build :  docker build -t fastia-maintenance:dev .
# Run   :  docker run --rm -p 8000:8000 fastia-maintenance:dev
# Test  :  curl http://localhost:8000/health

FROM python:3.11-slim

# Pas de fichiers .pyc, et logs Python affichés immédiatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Fichier dépendances : reste en cache tant que requirements.txt ne change pas (rebuilds à chaque modif de code).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Code applicatif + modèle
COPY app/ ./app/
COPY model/ ./model/

EXPOSE 8000

# Bonus : Docker interroge /health toutes les 30 s
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
