import streamlit as st
import os
import base64
import asyncio
import json
import nest_asyncio
from dotenv import load_dotenv

from utils import (
    pdf_to_images,
    encode_image,
    process_images_in_batches,
    merge_data,
    merge_soil_and_sample_data
)

from pydantic_models import MetadataAndSoilData, MetadataAndSampleData
from prompts import prompt_soil_data, prompt_sample_data

# Load environment variables
load_dotenv()
base_url = os.getenv("BASE_URL", "")
api_key = os.getenv("API_KEY", "")

nest_asyncio.apply()

if not os.path.exists("temp_pdf"):
    os.makedirs("temp_pdf")

def create_directories(pdf_path):
    output_dir = os.path.splitext(pdf_path)[0]
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def handle_pdf_upload():
    uploaded_pdf = st.file_uploader("📄 Upload Geotechnical PDF", type="pdf")
    
    if uploaded_pdf:
        pdf_path = f"temp_pdf/{uploaded_pdf.name}"
        with open(pdf_path, "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        st.success(f"✅ PDF uploaded: {uploaded_pdf.name}")
        
        if "final_data" not in st.session_state:
            # Process only once
            output_dir = create_directories(pdf_path)
            st.info("🔄 Converting PDF to images...")
            pdf_to_images(pdf_path, output_dir, fixed_length=3000, max_workers=4)

            image_files = sorted([
                os.path.join(output_dir, f) 
                for f in os.listdir(output_dir) 
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            ])
            
            if not image_files:
                st.error("❌ No image files found after PDF conversion.")
                return
            
            image_base64_list = [encode_image(image_path) for image_path in image_files]

            st.info("⚙️ Processing images through the model...")
            try:
                soil_data, sample_data = asyncio.run(process_images_in_batches(image_base64_list, base_url, api_key))
            except Exception as e:
                st.error(f"❌ Error during batch processing: {e}")
                return

            st.info("🧩 Merging parsed data...")
            try:
                merged_soil_data, merged_sample_data = merge_data(soil_data, sample_data, debug=True)
                final_data = merge_soil_and_sample_data(merged_soil_data, merged_sample_data)
                st.session_state["final_data"] = final_data
            except Exception as e:
                st.error(f"❌ Error during merging data: {e}")
                return

        display_hole_buttons(st.session_state["final_data"])

def display_hole_buttons(final_data):
    hole_numbers = set(item['metadata'].get('HOLE_NO', 'UNKNOWN') for item in final_data)
    st.subheader("🕳️ Select a HOLE_NO to view data:")
    
    for hole_no in sorted(hole_numbers):
        if st.button(f"View Data for HOLE_NO: {hole_no}"):
            st.session_state["selected_hole"] = hole_no

    if "selected_hole" in st.session_state:
        selected_data = [
            item for item in final_data 
            if item['metadata'].get('HOLE_NO') == st.session_state["selected_hole"]
        ]
        st.json(selected_data)

def main():
    st.title("🧠 Geotechnical Report Analysis Agent")
    handle_pdf_upload()

if __name__ == "__main__":
    main()
