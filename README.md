# Rhino Certification - Test Batch Upload

Application Streamlit pour tester l'upload de photos en lots vers l'API de certification Rhino.

## Fonctionnalites

- Telechargement d'images de test depuis Lorem Picsum
- Compression des images cote client (Python/Pillow)
- Upload par lots de 4 photos
- Barre de progression en temps reel
- Logs detailles
- Statistiques (temps, donnees envoyees, vitesse)

## Installation locale

```bash
# Cloner le repo ou naviguer vers le dossier
cd streamlit-test-upload

# Installer les dependances
pip install -r requirements.txt

# Lancer l'application
streamlit run app.py
```

## Deploiement sur Streamlit Cloud

1. **Pousser le code sur GitHub**
   - Creez un nouveau repo GitHub
   - Poussez le contenu de ce dossier

2. **Deployer sur Streamlit Cloud**
   - Allez sur [share.streamlit.io](https://share.streamlit.io)
   - Connectez votre compte GitHub
   - Selectionnez le repo et le fichier `app.py`
   - Cliquez sur "Deploy"

3. **Configuration des secrets (optionnel)**

   Dans Streamlit Cloud, vous pouvez configurer des secrets dans les parametres de l'app:

   ```toml
   API_URL = "https://dev.rhinocertification.com/api"
   API_KEY = "votre_cle_api"
   ```

## Utilisation

1. Configurez l'URL de l'API et la cle API
2. Ajustez la taille des images et la qualite de compression
3. Cliquez sur un bouton de test (10, 50, 100, 200 images)
4. Observez la progression et les logs
5. Le certificat PDF sera genere a la fin du test

## Structure des fichiers

```
streamlit-test-upload/
├── app.py              # Application principale
├── requirements.txt    # Dependances Python
├── README.md          # Documentation
└── .streamlit/
    └── config.toml    # Configuration Streamlit (theme)
```

## API Endpoints utilises

- `POST /external/v1/certify/start-session` - Demarrer une session
- `POST /external/v1/certify/upload-batch/{session_uuid}` - Envoyer un lot de photos
- `POST /external/v1/certify/finalize/{session_uuid}` - Finaliser et generer le PDF
