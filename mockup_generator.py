import streamlit as st
from PIL import Image
import io
import zipfile
import os

st.set_page_config(page_title="Shirt Mockup Generator", layout="wide")

st.title("👕 Shirt Mockup Generator")

# --- Caching Images to Speed Up ---
@st.cache_data
def load_image(img_file):
    return Image.open(img_file).convert("RGBA")

def overlay_design_on_mockup(mockup, design):
    mockup = mockup.copy()
    design = design.resize(mockup.size)
    mockup.alpha_composite(design)
    return mockup

# --- Upload Sections ---
col1, col2 = st.columns(2)

with col1:
    mockup_files = st.file_uploader("Upload Shirt Images (Mockups)", type=["png", "jpg"], accept_multiple_files=True)

with col2:
    design_files = st.file_uploader("Upload Designs", type=["png"], accept_multiple_files=True)

# --- Live Preview & Selection ---
if mockup_files and design_files:
    st.subheader("📌 Live Preview (Select mockups to download)")
    selected_images = []
    previews = []

    for m_file in mockup_files:
        mockup_img = load_image(m_file)

        for d_file in design_files:
            design_img = load_image(d_file)
            combined_img = overlay_design_on_mockup(mockup_img, design_img)

            img_bytes = io.BytesIO()
            combined_img.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            label = f"{os.path.splitext(m_file.name)[0]}_{os.path.splitext(d_file.name)[0]}.png"
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.image(combined_img, caption=label, use_container_width=True)
            with col_b:
                if st.checkbox(f"Select {label}", key=label):
                    selected_images.append((label, img_bytes))

    # --- Download Button for Selected ---
    if selected_images:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for img_name, img_bytes in selected_images:
                zipf.writestr(img_name, img_bytes.getvalue())
        zip_buffer.seek(0)
        st.download_button(
            label="📥 Download Selected Mockups as ZIP",
            data=zip_buffer,
            file_name="selected_mockups.zip",
            mime="application/zip"
        )
else:
    st.info("Please upload at least one mockup image and one design to start.")
