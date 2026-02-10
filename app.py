"""
Rhino Certification - Test Batch Upload
Streamlit app for testing batch photo upload to the certification API.
"""

import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import base64
import time
from datetime import datetime

# Configuration
BATCH_SIZE = 20
IMAGE_MAX_WIDTH = 720
COMPRESSION_QUALITY = 80
DEFAULT_API_URL = "https://dev.rhinocertification.com/api"

# Use Streamlit secrets if available, otherwise use empty string
DEFAULT_API_KEY = st.secrets.get("RHINO_API_KEY", "")
GOOGLE_MAPS_API_KEY = st.secrets.get("GOOGLE_MAPS_API_KEY", "")

st.set_page_config(
    page_title="Rhino - Test Batch Upload",
    page_icon="🦏",
    layout="wide"
)

# Initialize session state
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'stats' not in st.session_state:
    st.session_state.stats = {'photos': 0, 'time': 0, 'size': 0}


def format_logs(logs):
    """Format logs as text with colors."""
    lines = []
    for entry in logs:
        color = {
            'error': '🔴',
            'success': '🟢',
            'info': '🔵',
            '': '⚪'
        }.get(entry['type'], '⚪')
        lines.append(f"{color} [{entry['time']}] {entry['message']}")
    return "\n".join(lines) if lines else "En attente..."


def fetch_picsum_image(index: int, size: int) -> bytes:
    """Fetch a random image from Lorem Picsum."""
    url = f"https://picsum.photos/{size}/{size}?random={index}&t={int(time.time() * 1000)}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def compress_image(image_bytes: bytes) -> str:
    """Compress image and return base64 encoded string."""
    img = Image.open(BytesIO(image_bytes))

    # Resize if needed
    if img.width > IMAGE_MAX_WIDTH:
        ratio = IMAGE_MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((IMAGE_MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Compress to JPEG
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=COMPRESSION_QUALITY, optimize=True)
    compressed_bytes = buffer.getvalue()

    return base64.b64encode(compressed_bytes).decode('utf-8')


def run_test(count: int, api_url: str, api_key: str, customer_name: str, customer_address: str, lat: float, lng: float, progress_bar, status_text, log_placeholder):
    """Run the batch upload test with real-time log updates."""
    logs = []

    def log(message: str, log_type: str = ""):
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append({'time': timestamp, 'message': message, 'type': log_type})
        # Update log display in real-time
        log_placeholder.code(format_logs(logs), language=None)

    total_data_sent = 0
    start_time = time.time()

    log("=" * 40, "info")
    log(f"[TEST] STARTING TEST: {count} images", "info")
    log(f"[TEST] API: {api_url}", "info")
    log(f"[TEST] Client: {customer_name}", "info")
    log(f"[TEST] Adresse: {customer_address}", "info")
    log(f"[TEST] GPS: {lat}, {lng}", "info")
    log(f"[TEST] Max width: {IMAGE_MAX_WIDTH}px, Quality: {COMPRESSION_QUALITY}, Batch size: {BATCH_SIZE}", "info")
    log("=" * 40, "info")

    try:
        # Step 0: Download images from Picsum
        status_text.text("Downloading test images...")
        log(f"[FETCH] Downloading {count} images from Picsum...", "info")

        images = []
        for i in range(count):
            progress_bar.progress((i + 1) / count, text=f"Downloading image {i + 1}/{count}...")
            image_bytes = fetch_picsum_image(i, IMAGE_MAX_WIDTH)
            images.append(image_bytes)
            size_kb = len(image_bytes) / 1024
            log(f"[FETCH] Image {i + 1} downloaded: {size_kb:.1f} KB")

        log(f"[FETCH] {count} images downloaded!", "success")

        # Step 1: Start session
        log("[SESSION] Creating session...", "info")
        status_text.text("Creating session...")
        progress_bar.progress(0, text="Creating session...")

        start_response = requests.post(
            f"{api_url}/external/v1/certify/start-session",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json={
                'customer_name': customer_name,
                'customer_address': customer_address,
                'latitude': lat,
                'longitude': lng,
                'expected_photos_count': count
            },
            timeout=30
        )

        if not start_response.ok:
            error = start_response.json()
            raise Exception(error.get('detail', 'Error creating session'))

        session_uuid = start_response.json()['session_uuid']
        log(f"[SESSION] Session created: {session_uuid}", "success")

        # Step 2: Upload in batches
        total_batches = (count + BATCH_SIZE - 1) // BATCH_SIZE
        log(f"[BATCH] Starting upload: {count} photos in {total_batches} batches", "info")

        for batch_index in range(total_batches):
            start_idx = batch_index * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, count)
            batch_images = images[start_idx:end_idx]

            log(f"[BATCH] === Batch {batch_index + 1}/{total_batches} ({len(batch_images)} photos) ===", "info")

            # Compress photos
            compressed_photos = []
            for i, img_bytes in enumerate(batch_images):
                progress_bar.progress(
                    (start_idx + i + 1) / count,
                    text=f"Compressing {start_idx + i + 1}/{count}..."
                )
                compressed = compress_image(img_bytes)
                compressed_photos.append(compressed)
                compressed_size_kb = len(compressed) * 3 / 4 / 1024
                log(f"[COMPRESS] Photo {start_idx + i + 1}: ~{compressed_size_kb:.1f} KB")

            # Calculate batch size
            batch_size_bytes = sum(len(p) * 3 / 4 for p in compressed_photos)
            total_data_sent += batch_size_bytes
            log(f"[BATCH] Sending batch {batch_index + 1}: {len(batch_images)} photos, ~{batch_size_bytes / 1024:.1f} KB")

            status_text.text(f"Sending batch {batch_index + 1}/{total_batches}...")

            # Send batch
            batch_response = requests.post(
                f"{api_url}/external/v1/certify/upload-batch/{session_uuid}",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                },
                json={
                    'photos': compressed_photos,
                    'batch_index': batch_index
                },
                timeout=120
            )

            if not batch_response.ok:
                error = batch_response.json()
                log(f"[BATCH] ERROR: Batch {batch_index + 1} failed: {error.get('detail', 'Unknown error')}", "error")
                raise Exception(error.get('detail', 'Error uploading batch'))

            result = batch_response.json()
            log(f"[BATCH] Batch {batch_index + 1} complete. Total uploaded: {result['total_uploaded']}", "success")

        log("[BATCH] All batches sent successfully!", "success")

        # Step 3: Finalize
        log("[FINALIZE] Finalizing...", "info")
        status_text.text("Generating PDF certificate...")
        progress_bar.progress(1.0, text="Generating PDF...")

        finalize_response = requests.post(
            f"{api_url}/external/v1/certify/finalize/{session_uuid}",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            timeout=300
        )

        if not finalize_response.ok:
            error = finalize_response.json()
            raise Exception(error.get('detail', 'Error finalizing'))

        data = finalize_response.json()
        total_time = time.time() - start_time

        log("=" * 40, "success")
        log("[TEST] ✅ TEST SUCCESSFUL!", "success")
        log(f"[TEST] Certificate UUID: {data['certificate_uuid']}", "success")
        log(f"[TEST] PDF URL: {data['pdf_url']}", "success")
        log(f"[TEST] Photos: {data['photos_count']}", "success")
        log(f"[TEST] Credits remaining: {data['credits_remaining']}", "success")
        log(f"[TEST] Total time: {total_time:.1f}s", "success")
        log(f"[TEST] Data sent: {total_data_sent / 1024 / 1024:.2f} MB", "success")
        log(f"[TEST] Average speed: {count / total_time:.1f} photos/sec", "success")
        log("=" * 40, "success")

        status_text.text("✅ Test completed successfully!")
        st.session_state.stats = {
            'photos': count,
            'time': total_time,
            'size': total_data_sent
        }
        st.session_state.logs = logs

        return data

    except Exception as e:
        total_time = time.time() - start_time
        log("=" * 40, "error")
        log(f"[TEST] ❌ TEST FAILED: {str(e)}", "error")
        log("=" * 40, "error")
        status_text.text(f"❌ Error: {str(e)}")
        st.session_state.stats = {
            'photos': 0,
            'time': total_time,
            'size': total_data_sent
        }
        st.session_state.logs = logs
        return None


# UI
st.title("🦏 Test Batch Upload")

# Configuration section
with st.expander("Configuration API", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        api_url = st.text_input("API URL", value=DEFAULT_API_URL)
    with col2:
        api_key = st.text_input("API Key", value=DEFAULT_API_KEY, type="password")
    st.caption(f"Max width: {IMAGE_MAX_WIDTH}px | Quality: {COMPRESSION_QUALITY}% | Batch: {BATCH_SIZE} photos")

# Initialize geocoded coordinates in session state
if 'geocoded_lat' not in st.session_state:
    st.session_state.geocoded_lat = "48.8566"
if 'geocoded_lng' not in st.session_state:
    st.session_state.geocoded_lng = "2.3522"

# Customer info section
st.subheader("Informations client")

customer_name = st.text_input("Nom du client *", value="Test Batch Upload")

col1, col2 = st.columns([3, 1])
with col1:
    customer_address = st.text_input("Adresse complète", value="123 rue de Paris, 75001 Paris")
with col2:
    st.write("")  # Spacing
    geocode_btn = st.button("📍 Générer GPS", use_container_width=True)

if geocode_btn and customer_address:
    try:
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={requests.utils.quote(customer_address)}&key={GOOGLE_MAPS_API_KEY}"
        geocode_response = requests.get(geocode_url, timeout=10)
        geocode_data = geocode_response.json()

        if geocode_data.get('status') == 'OK' and geocode_data.get('results'):
            location = geocode_data['results'][0]['geometry']['location']
            st.session_state.geocoded_lat = str(location['lat'])
            st.session_state.geocoded_lng = str(location['lng'])
            st.success(f"Coordonnées trouvées: {location['lat']}, {location['lng']}")
            st.rerun()
        else:
            st.error(f"Geocoding échoué: {geocode_data.get('status', 'Unknown error')}")
    except Exception as e:
        st.error(f"Erreur: {str(e)}")

col1, col2 = st.columns(2)
with col1:
    latitude = st.text_input("Latitude", value=st.session_state.geocoded_lat)
with col2:
    longitude = st.text_input("Longitude", value=st.session_state.geocoded_lng)

# Test buttons
st.subheader("Run Tests")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    test_10 = st.button("Test 10 images", disabled=st.session_state.is_running)
with col2:
    test_50 = st.button("Test 50 images", disabled=st.session_state.is_running)
with col3:
    test_100 = st.button("Test 100 images", disabled=st.session_state.is_running)
with col4:
    test_200 = st.button("Test 200 images", disabled=st.session_state.is_running)
with col5:
    custom_count = st.number_input("Custom", min_value=1, max_value=1000, value=25, label_visibility="collapsed")
    test_custom = st.button("Run custom", disabled=st.session_state.is_running)

# Progress section
progress_bar = st.progress(0, text="Ready...")
status_text = st.empty()

# Stats
st.subheader("Statistics")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Photos sent", st.session_state.stats['photos'])
with col2:
    st.metric("Total time", f"{st.session_state.stats['time']:.1f}s")
with col3:
    st.metric("Data sent", f"{st.session_state.stats['size'] / 1024 / 1024:.2f} MB")

# Logs section
st.subheader("Logs")

col1, col2 = st.columns([6, 1])
with col2:
    if st.button("Clear logs"):
        st.session_state.logs = []
        st.rerun()

# Log placeholder for real-time updates
log_placeholder = st.empty()
log_placeholder.code(format_logs(st.session_state.logs), language=None)

# Parse coordinates
try:
    lat = float(latitude) if latitude else 48.8566
    lng = float(longitude) if longitude else 2.3522
except ValueError:
    lat, lng = 48.8566, 2.3522

# Handle button clicks
if test_10:
    st.session_state.is_running = True
    run_test(10, api_url, api_key, customer_name, customer_address, lat, lng, progress_bar, status_text, log_placeholder)
    st.session_state.is_running = False
    st.rerun()
elif test_50:
    st.session_state.is_running = True
    run_test(50, api_url, api_key, customer_name, customer_address, lat, lng, progress_bar, status_text, log_placeholder)
    st.session_state.is_running = False
    st.rerun()
elif test_100:
    st.session_state.is_running = True
    run_test(100, api_url, api_key, customer_name, customer_address, lat, lng, progress_bar, status_text, log_placeholder)
    st.session_state.is_running = False
    st.rerun()
elif test_200:
    st.session_state.is_running = True
    run_test(200, api_url, api_key, customer_name, customer_address, lat, lng, progress_bar, status_text, log_placeholder)
    st.session_state.is_running = False
    st.rerun()
elif test_custom:
    st.session_state.is_running = True
    run_test(custom_count, api_url, api_key, customer_name, customer_address, lat, lng, progress_bar, status_text, log_placeholder)
    st.session_state.is_running = False
    st.rerun()
