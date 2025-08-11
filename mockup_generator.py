import streamlit as st
from PIL import Image
import numpy as np
import zipfile
import io
import cv2
import os
import gc

st.set_page_config(page_title="Shirt Mockup Generator", layout="centered")
st.title("👕 Shirt Mockup Generator with Batching")

st.markdown("""
Upload multiple design PNGs and shirt templates.  
Preview placement and generate mockups in batches without crashing.
""")

# --- Sidebar Controls ---
plain_padding_ratio = st.sidebar.slider("Padding Ratio – Plain Shirt", 0.1, 1.0, 0.45, 0.05)
model_padding_ratio = st.sidebar.slider("Padding Ratio – Model Shirt", 0.1, 1.0, 0.45, 0.05)
plain_offset_pct = st.sidebar.slider("Vertical Offset – Plain Shirt (%)", -50, 100, 24, 1)
model_offset_pct = st.sidebar.slider("Vertical Offset – Model Shirt (%)", -50, 100, 38, 1)
resize_width = st.sidebar.number_input("Resize shirt width (px, 0 = no resize)", 0, 5000, 0, step=100)

# --- Session Setup ---
if "design_names" not in st.session_state:
    st.session_state.design_names = {}
if "shirt_bboxes" not in st.session_state:
    st.session_state.shirt_bboxes = {}

# --- Upload Section ---
design_files = st.file_uploader("📌 Upload Design Images", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
shirt_files = st.file_uploader("🎨 Upload Shirt Templates", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

# --- Clear Button ---
if st.button("🔄 Start Over"):
    st.session_state.design_names.clear()
    st.session_state.shirt_bboxes.clear()
    st.rerun()

# --- Design Naming ---
if design_files:
    st.markdown("### ✏️ Name Each Design")
    for i, file in enumerate(design_files):
        default_name = os.path.splitext(file.name)[0]
        custom_name = st.text_input(
            f"Name for Design {i+1} ({file.name})",
            value=st.session_state.design_names.get(file.name, default_name),
            key=f"name_input_{i}_{file.name}"
        )
        st.session_state.design_names[file.name] = custom_name

# --- Batch Controls ---
if design_files:
    st.markdown("### 📦 Batch Processing Control")
    total_designs = len(design_files)
    batch_start = st.number_input("Start from Design #", min_value=1, max_value=total_designs, value=1)
    batch_end = st.number_input("End at Design #", min_value=batch_start, max_value=total_designs, value=min(batch_start + 19, total_designs))
    selected_batch = design_files[batch_start - 1: batch_end]

# --- Bounding Box Detection (cached) ---
def get_shirt_bbox_cached(shirt_bytes, shirt_name):
    if shirt_name in st.session_state.shirt_bboxes:
        return st.session_state.shirt_bboxes[shirt_name]

    with Image.open(io.BytesIO(shirt_bytes)).convert("RGB") as pil_image:
        img_cv = np.array(pil_image)[:, :, ::-1]
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bbox = cv2.boundingRect(max(contours, key=cv2.contourArea)) if contours else None

    st.session_state.shirt_bboxes[shirt_name] = bbox
    return bbox

# --- Live Preview ---
if design_files and shirt_files:
    st.markdown("### 👀 Live Preview")
    selected_design = st.selectbox("Select a Design", design_files, format_func=lambda x: x.name)
    selected_shirt = st.selectbox("Select a Shirt Template", shirt_files, format_func=lambda x: x.name)

    try:
        selected_design.seek(0)
        with Image.open(selected_design).convert("RGBA") as design:
            selected_shirt.seek(0)
            with Image.open(selected_shirt).convert("RGBA") as shirt:

                # Optional resize for memory savings
                if resize_width > 0 and shirt.width > resize_width:
                    new_height = int(shirt.height * (resize_width / shirt.width))
                    shirt = shirt.resize((resize_width, new_height), Image.LANCZOS)

                is_model = "model" in selected_shirt.name.lower()
                offset_pct = model_offset_pct if is_model else plain_offset_pct
                padding_ratio = model_padding_ratio if is_model else plain_padding_ratio

                bbox = get_shirt_bbox_cached(selected_shirt.getvalue(), selected_shirt.name)
                if bbox:
                    sx, sy, sw, sh = bbox
                    scale = min(sw / design.width, sh / design.height, 1.0) * padding_ratio
                    new_width = int(design.width * scale)
                    new_height = int(design.height * scale)
                    resized_design = design.resize((new_width, new_height))
                    y_offset = int(sh * offset_pct / 100)
                    x = sx + (sw - new_width) // 2
                    y = sy + y_offset
                else:
                    resized_design = design
                    x = (shirt.width - design.width) // 2
                    y = (shirt.height - design.height) // 2

                preview = shirt.copy()
                preview.paste(resized_design, (x, y), resized_design)
                st.image(preview, caption="📸 Live Mockup Preview", use_container_width=True)

    except Exception as e:
        st.error(f"⚠️ Preview failed: {e}")

# --- Generate Mockups (optimized) ---
if st.button("🚀 Generate Mockups for Selected Batch"):
    if not (selected_batch and shirt_files):
        st.warning("Upload at least one design and one shirt template.")
    else:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for design_file in selected_batch:
                design_name = st.session_state.design_names.get(design_file.name, "graphic")

                design_file.seek(0)
                with Image.open(design_file).convert("RGBA") as design:
                    for shirt_file in shirt_files:
                        shirt_name = os.path.splitext(shirt_file.name)[0]

                        shirt_file.seek(0)
                        with Image.open(shirt_file).convert("RGBA") as shirt:

                            # Optional resize for memory savings
                            if resize_width > 0 and shirt.width > resize_width:
                                new_height = int(shirt.height * (resize_width / shirt.width))
                                shirt = shirt.resize((resize_width, new_height), Image.LANCZOS)

                            is_model = "model" in shirt_file.name.lower()
                            offset_pct = model_offset_pct if is_model else plain_offset_pct
                            padding_ratio = model_padding_ratio if is_model else plain_padding_ratio

                            bbox = get_shirt_bbox_cached(shirt_file.getvalue(), shirt_file.name)
                            if bbox:
                                sx, sy, sw, sh = bbox
                                scale = min(sw / design.width, sh / design.height, 1.0) * padding_ratio
                                new_width = int(design.width * scale)
                                new_height = int(design.height * scale)
                                resized_design = design.resize((new_width, new_height))
                                y_offset = int(sh * offset_pct / 100)
                                x = sx + (sw - new_width) // 2
                                y = sy + y_offset
                            else:
                                resized_design = design
                                x = (shirt.width - design.width) // 2
                                y = (shirt.height - design.height) // 2

                            shirt_copy = shirt.copy()
                            shirt_copy.paste(resized_design, (x, y), resized_design)

                            img_byte_arr = io.BytesIO()
                            shirt_copy.save(img_byte_arr, format='PNG')
                            img_byte_arr.seek(0)

                            # Write directly into ZIP under folder for each design
                            zipf.writestr(f"{design_name}_{shirt_name}.png", img_byte_arr.getvalue())

                            # Clean up memory
                            del shirt_copy, resized_design, img_byte_arr
                            gc.collect()

        zip_buffer.seek(0)
        st.download_button(
            label="📦 Download All Mockups",
            data=zip_buffer,
            file_name="all_mockups.zip",
            mime="application/zip"
        )

