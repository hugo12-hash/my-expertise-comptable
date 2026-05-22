# 🧾 MY Expertise Comptable - Plateforme d'automatisation

Plateforme web modulaire pour automatiser les tâches comptables récurrentes.

## 📦 Modules disponibles

| Module | Statut | Description |
|--------|--------|-------------|
| 📄 Relevés bancaires | ✅ Disponible | Conversion PDF (scan ou natif) → Excel comptable avec contreparties 471/512 |

## 🚀 Démarrage rapide en local

```bash
# 1. Cloner le repo
git clone https://github.com/VOTRE_COMPTE/my-expertise-comptable.git
cd my-expertise-comptable

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate    # Mac/Linux
# OU
venv\Scripts\activate       # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
streamlit run app.py
```

L'app s'ouvre automatiquement sur `http://localhost:8501`.

## ☁️ Déploiement gratuit sur Streamlit Cloud

### Étape 1 — Mettre le code sur GitHub

1. Créer un compte sur [github.com](https://github.com) (gratuit)
2. Créer un nouveau dépôt **public** nommé `my-expertise-comptable`
3. Uploader tous les fichiers du projet

### Étape 2 — Déployer sur Streamlit Cloud

1. Aller sur [share.streamlit.io](https://share.streamlit.io)
2. Se connecter avec son compte GitHub
3. Cliquer sur **"New app"**
4. Sélectionner le dépôt `my-expertise-comptable`
5. Branche : `main`, Fichier principal : `app.py`
6. Cliquer sur **"Deploy"**

L'app sera accessible à une URL du type :
`https://my-expertise-comptable.streamlit.app`

### Étape 3 — Configurer la clé API Gemini (optionnel mais recommandé)

Pour les PDF scannés ou complexes, l'app utilise Gemini en backup.

1. Obtenir une clé API gratuite sur [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Dans Streamlit Cloud, cliquer sur **"Settings" → "Secrets"** de votre app
3. Ajouter :

```toml
GEMINI_API_KEY = "votre_cle_api_ici"
```

4. Sauvegarder — l'app redémarre automatiquement.

## 📊 Format de sortie du module Relevés bancaires

Chaque transaction du PDF génère **2 lignes** dans l'Excel (partie double) :

| DATE | PIECE | COMPTE | LIB | DEBIT | CREDIT |
|------|-------|--------|-----|-------|--------|
| 01/05/2026 |  | 51200000 | VIR CLIENT DUPONT | 1500.00 |  |
| 01/05/2026 |  | 47100000 | VIR CLIENT DUPONT |  | 1500.00 |

- **51200000** = compte banque (modifiable dans l'interface)
- **47100000** = compte contrepartie / attente (modifiable dans l'interface)
- **PIECE** = vide (à remplir manuellement après import)

## 🛠️ Ajouter un nouveau module

1. Créer un fichier `pages/2_📊_Nom_Module.py`
2. Ajouter la logique dans `utils/`
3. Mettre à jour `app.py` pour activer la carte du module
4. Pousser sur GitHub → déploiement automatique

## 🔒 Sécurité

- Aucune authentification (à ajouter si besoin via `streamlit-authenticator`)
- Les fichiers sont traités **en mémoire** et ne sont **jamais stockés**
- La clé API Gemini est stockée dans les secrets Streamlit (chiffrée)

## 📝 Limites de la version gratuite

- **Streamlit Cloud** : app endormie après 7 jours sans visite (réveil en ~30s)
- **Gemini Flash** : 1500 requêtes/jour (largement suffisant pour ~70 pages/jour)
- **Taille fichier** : 200 Mo max par upload

---

*MY Expertise Comptable — Plateforme interne*
