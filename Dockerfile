# Image de base Python légère
FROM python:3.12-slim

# Installer les paquets système nécessaires :
# - tesseract-ocr + langue française (pour l'OCR des relevés scannés)
# - poppler-utils (pour convertir les PDF en images)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Dossier de travail dans le conteneur
WORKDIR /app

# Copier d'abord requirements.txt (pour profiter du cache Docker)
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le reste du projet
COPY . .

# Render fournit le port via la variable d'environnement $PORT
# Streamlit doit écouter sur 0.0.0.0 et sur ce port
EXPOSE 8501

# Commande de démarrage
# On utilise la forme shell pour que $PORT soit bien interprété
CMD streamlit run app.py \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=true
