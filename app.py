import streamlit as st
import base64
import requests
from PIL import Image
from io import BytesIO

# Configuration API Rhino
API_URL = "https://app.rhinocertification.com/api"
API_KEY = st.secrets.get("RHINO_API_KEY", "")

# Configuration API Google Maps
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

# Configuration compression
BATCH_SIZE = 20
IMAGE_MAX_WIDTH = 720
COMPRESSION_QUALITY = 80


# Fonction pour obtenir les coordonnées GPS à partir d'une adresse
def get_coordinates(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']
    return None, None


def compress_image(image_bytes: bytes) -> str:
    """Compress image and return base64 encoded string."""
    img = Image.open(BytesIO(image_bytes))

    if img.width > IMAGE_MAX_WIDTH:
        ratio = IMAGE_MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=COMPRESSION_QUALITY, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


# Interface utilisateur Streamlit
st.title("Formulaire de dépôt Rhino Certification pour ENERGIE RESPONSABLE")

client_name = st.text_input("Nom du client")
address = st.text_input("Adresse complète (ex: 123 rue Exemple, Paris, France)")

# Initialisation des champs Latitude et Longitude
latitude = st.session_state.get("latitude", "")
longitude = st.session_state.get("longitude", "")

# Bouton pour générer automatiquement les coordonnées GPS
if st.button("Générer les coordonnées GPS"):
    if address:
        lat, lng = get_coordinates(address)
        if lat is not None and lng is not None:
            st.session_state["latitude"] = str(lat)
            st.session_state["longitude"] = str(lng)
            latitude = str(lat)
            longitude = str(lng)
        else:
            st.error("Impossible de générer les coordonnées GPS pour l'adresse fournie.")

# Champs Latitude et Longitude pré-remplis
latitude = st.text_input("Latitude", value=latitude)
longitude = st.text_input("Longitude", value=longitude)

uploaded_files = st.file_uploader("Téléchargez les photos (JPEG/PNG)", accept_multiple_files=True, type=["jpg", "png"])

if st.button("Soumettre"):
    if not client_name or not address or not latitude or not longitude or not uploaded_files:
        st.error("Veuillez remplir tous les champs et télécharger au moins une photo.")
    else:
        try:
            lat = float(latitude)
            lng = float(longitude)
        except ValueError:
            st.error("Latitude et Longitude doivent être des nombres valides.")
            st.stop()

        st.info("Préparation de l'envoi...")

        # Lire les images uploadées
        images = []
        for file in uploaded_files:
            images.append(file.read())

        count = len(images)

        # Step 1: Créer la session
        st.info("Création de la session...")
        start_response = requests.post(
            f"{API_URL}/external/v1/certify/start-session",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            json={
                'customer_name': client_name,
                'customer_address': address,
                'latitude': lat,
                'longitude': lng,
                'expected_photos_count': count
            },
            timeout=30
        )

        if not start_response.ok:
            error = start_response.json()
            st.error(f"Erreur création session: {error.get('detail', 'Erreur inconnue')}")
            st.stop()

        session_uuid = start_response.json()['session_uuid']

        # Step 2: Upload par batch
        total_batches = (count + BATCH_SIZE - 1) // BATCH_SIZE
        st.info(f"Envoi de {count} photos...")

        for batch_index in range(total_batches):
            start_idx = batch_index * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, count)
            batch_images = images[start_idx:end_idx]

            compressed_photos = []
            for img_bytes in batch_images:
                compressed_photos.append(compress_image(img_bytes))

            batch_response = requests.post(
                f"{API_URL}/external/v1/certify/upload-batch/{session_uuid}",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {API_KEY}'
                },
                json={
                    'photos': compressed_photos,
                    'batch_index': batch_index
                },
                timeout=120
            )

            if not batch_response.ok:
                error = batch_response.json()
                st.error(f"Erreur batch {batch_index + 1}: {error.get('detail', 'Erreur inconnue')}")
                st.stop()

        # Step 3: Finaliser
        st.info("Finalisation et génération du certificat PDF...")
        finalize_response = requests.post(
            f"{API_URL}/external/v1/certify/finalize/{session_uuid}",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}'
            },
            timeout=300
        )

        if not finalize_response.ok:
            error = finalize_response.json()
            st.error(f"Erreur finalisation: {error.get('detail', 'Erreur inconnue')}")
            st.stop()

        data = finalize_response.json()
        st.success("Données envoyées avec succès !")
