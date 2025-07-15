import streamlit as st
import os
import base64
import asyncio
import json
import tempfile
import shutil
from pathlib import Path

from utils import (
    pdf_to_images,
    encode_image,
    process_images_in_batches,
    merge_data,
    merge_soil_and_sample_data
)

from pydantic_models import MetadataAndSoilData, MetadataAndSampleData
from prompts import prompt_soil_data, prompt_sample_data

# Configure Streamlit page
st.set_page_config(
    page_title="Geotechnical Report Analysis",
    page_icon="🧠",
    layout="wide"
)

@st.cache_data
def get_config():
    """Get configuration from Streamlit secrets"""
    try:
        base_url = st.secrets["BASE_URL"]
        api_key = st.secrets["API_KEY"]
        return base_url, api_key
    except KeyError as e:
        st.error(f"❌ Missing secret: {e}. Please configure secrets in Streamlit Cloud.")
        st.stop()

@st.cache_data
def process_pdf_to_images(pdf_bytes, filename):
    """Process PDF to images with caching and temporary directories"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save uploaded PDF to temporary file
        pdf_path = os.path.join(temp_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        
        # Create output directory for images
        output_dir = os.path.join(temp_dir, "images")
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert PDF to images (reduced workers for cloud)
        pdf_to_images(pdf_path, output_dir, fixed_length=3000, max_workers=2)
        
        # Get all image files
        image_files = sorted([
            os.path.join(output_dir, f) 
            for f in os.listdir(output_dir) 
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ])
        
        if not image_files:
            return None
        
        # Encode images to base64
        image_base64_list = []
        for image_path in image_files:
            try:
                encoded_image = encode_image(image_path)
                image_base64_list.append(encoded_image)
            except Exception as e:
                st.warning(f"⚠️ Failed to encode image {os.path.basename(image_path)}: {e}")
                continue
        
        return image_base64_list

async def process_images_async(image_base64_list, base_url, api_key):
    """Async wrapper for image processing"""
    try:
        return await process_images_in_batches(image_base64_list, base_url, api_key)
    except Exception as e:
        st.error(f"❌ Error during batch processing: {e}")
        return None, None

def display_hole_data(final_data):
    """Display hole data with improved UI"""
    if not final_data:
        st.warning("⚠️ No data available to display.")
        return
    
    # Get unique hole numbers
    hole_numbers = set()
    for item in final_data:
        hole_no = item.get('metadata', {}).get('HOLE_NO', 'UNKNOWN')
        hole_numbers.add(hole_no)
    
    hole_numbers = sorted(hole_numbers)
    
    if not hole_numbers:
        st.warning("⚠️ No hole numbers found in the data.")
        return
    
    st.subheader("🕳️ Select a HOLE_NO to view data:")
    
    # Use columns for better layout
    cols = st.columns(min(len(hole_numbers), 4))
    
    for i, hole_no in enumerate(hole_numbers):
        with cols[i % 4]:
            if st.button(f"HOLE {hole_no}", key=f"hole_{hole_no}"):
                st.session_state["selected_hole"] = hole_no

    # Display selected hole data
    if "selected_hole" in st.session_state:
        selected_hole = st.session_state["selected_hole"]
        selected_data = [
            item for item in final_data 
            if item.get('metadata', {}).get('HOLE_NO') == selected_hole
        ]
        
        if selected_data:
            st.subheader(f"📊 Data for HOLE_NO: {selected_hole}")
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔍 Detailed View", "📄 Raw JSON"])
            
            with tab1:
                display_summary_view(selected_data)
            
            with tab2:
                display_detailed_view(selected_data)
            
            with tab3:
                st.json(selected_data)
        else:
            st.error(f"❌ No data found for HOLE_NO: {selected_hole}")

def display_summary_view(data):
    """Display a summary view of the data"""
    st.write(f"**Total Records:** {len(data)}")
    
    # Count different data types
    soil_count = sum(1 for item in data if 'soil_data' in item)
    sample_count = soil_count
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🏔️ Soil Data Records", soil_count)
    with col2:
        st.metric("🧪 Sample Data Records", sample_count)

def display_detailed_view(data):
    """Display detailed view with expandable sections"""
    for i, item in enumerate(data):
        with st.expander(f"Record {i+1} - {item.get('metadata', {}).get('HOLE_NO', 'Unknown')}"):
            
            # Metadata
            if 'metadata' in item:
                st.subheader("📋 Metadata")
                metadata_cols = st.columns(3)
                metadata = item['metadata']
                
                with metadata_cols[0]:
                    st.write(f"**HOLE_NO:** {metadata.get('HOLE_NO', 'N/A')}")
                    st.write(f"**PROJECT:** {metadata.get('PROJECT_NAME', 'N/A')}")
                
                with metadata_cols[1]:
                    st.write(f"**DATE:** {metadata.get('DATE', 'N/A')}")
                    st.write(f"**LOCATION:** {metadata.get('LOCATION', 'N/A')}")
                
                with metadata_cols[2]:
                    st.write(f"**EXCAVATION_LEVEL:** {metadata.get('Excavation_level', 'N/A')}")
                    st.write(f"**DRILLER:** {metadata.get('DRILLER', 'N/A')}")
            
            # Soil Data
            if 'soil_data' in item:
                st.subheader("🏔️ Soil Data")
                st.json(item['soil_data'])
            
            # Sample Data
            if 'sample_data' in item:
                st.subheader("🧪 Sample Data")
                st.json(item['sample_data'])

def handle_pdf_upload():
    """Handle PDF upload and processing"""
    base_url, api_key = get_config()
    
    uploaded_pdf = st.file_uploader(
        "📄 Upload Geotechnical PDF", 
        type="pdf",
        help="Upload a geotechnical report in PDF format for analysis"
    )
    
    if uploaded_pdf:
        # Display file info
        file_size_mb = len(uploaded_pdf.getvalue()) / (1024 * 1024)
        st.success(f"✅ PDF uploaded: {uploaded_pdf.name} ({file_size_mb:.1f} MB)")
        
        # Check file size limit (adjust as needed)
        if file_size_mb > 50:
            st.error("❌ File too large. Please upload a PDF smaller than 50MB.")
            return
        
        # Process PDF if not already done
        cache_key = f"{uploaded_pdf.name}_{len(uploaded_pdf.getvalue())}"
        
        if f"final_data_{cache_key}" not in st.session_state:
            with st.spinner("🔄 Processing PDF..."):
                progress_bar = st.progress(0)
                
                # Step 1: Convert PDF to images
                st.info("📷 Converting PDF to images...")
                progress_bar.progress(20)
                
                image_base64_list = process_pdf_to_images(
                    uploaded_pdf.getvalue(), 
                    uploaded_pdf.name
                )
                
                if not image_base64_list:
                    st.error("❌ No images could be extracted from the PDF.")
                    return
                
                progress_bar.progress(40)
                st.success(f"✅ Extracted {len(image_base64_list)} images from PDF")
                
                # Step 2: Process images through model
                st.info("⚙️ Processing images through AI model...")
                progress_bar.progress(60)
                
                try:
                    soil_data, sample_data = asyncio.run(
                        process_images_async(image_base64_list, base_url, api_key)
                    )
                    
                    if soil_data is None or sample_data is None:
                        st.error("❌ Failed to process images through AI model.")
                        return
                        
                except Exception as e:
                    st.error(f"❌ Error during AI processing: {e}")
                    return
                
                progress_bar.progress(80)
                
                # Step 3: Merge data
                st.info("🧩 Merging and structuring data...")
                
                try:
                    merged_soil_data, merged_sample_data = merge_data(
                        soil_data, sample_data, debug=False
                    )
                    final_data = merge_soil_and_sample_data(
                        merged_soil_data, merged_sample_data
                    )
                    
                    st.session_state[f"final_data_{cache_key}"] = final_data
                    progress_bar.progress(100)
                    st.success("✅ Processing complete!")
                    
                except Exception as e:
                    st.error(f"❌ Error during data merging: {e}")
                    return
        
        # Display results
        final_data = st.session_state.get(f"final_data_{cache_key}")
        if final_data:
            display_hole_data(final_data)

def main():
    """Main application function"""
    st.title("🧠 Geotechnical Report Analysis Agent")
    st.markdown("Upload a geotechnical PDF report with only drill log data to extract and analyze soil and sample data.")
    
    # Sidebar with info
    with st.sidebar:
        st.header("ℹ️ Information")
        st.markdown("""
        This application:
        - Converts PDF pages to images
        - Analyzes images using AI
        - Extracts soil and sample data
        - Organizes data by hole number
        
        **Supported formats:** PDF
        **Max file size:** 50MB
        """)
        
        if st.button("🗑️ Clear Cache"):
            for key in list(st.session_state.keys()):
                if key.startswith("final_data_") or key == "selected_hole":
                    del st.session_state[key]
            st.success("Cache cleared!")
            st.rerun()
    
    # Main content
    handle_pdf_upload()

if __name__ == "__main__":
    main()