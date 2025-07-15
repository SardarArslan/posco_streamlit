import os
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor
import base64
import openai
from io import BytesIO
import time
from collections import defaultdict
from typing import List
import re
import json
import asyncio
from PIL import Image
from pydantic_models import *
from prompts import prompt_soil_data, prompt_sample_data
def encode_image(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")  # Ensure it's RGB format
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    encoded_string = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return encoded_string

def process_page(page, scale, base_name, output_dir, page_number):
    # Render the page to an image (pixmap) using the transformation matrix
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix)

    # Define the output image path
    image_filename = f"{base_name}_page_{page_number + 1}.jpg"
    image_path = os.path.join(output_dir, image_filename)

    # Save the image in PNG format
    pix.save(image_path)
    return image_path

def pdf_to_images(pdf_path, output_dir, fixed_length=1080, max_workers=4):
    # Ensure the PDF file exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file {pdf_path} does not exist.")

    # Extract the base file name (without extension) for directory naming
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open the PDF file using fitz (PyMuPDF)
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {e}")

    # Get the original width and height of the first page to calculate scale
    original_width = doc[0].rect.width

    # Calculate the scaling factor to achieve the fixed height (length)
    scale = fixed_length / original_width

    # Create a list to hold the future results of the image processing
    file_paths = []

    # Use ThreadPoolExecutor to process pages concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_page, doc[page_number], scale, base_name, output_dir, page_number)
            for page_number in range(len(doc))
        ]

        # Collect results
        file_paths = [future.result() for future in futures]

    # Close the document
    doc.close()

    print(f"PDF converted to images with fixed length {fixed_length}px and saved to: {output_dir}")
    return output_dir, file_paths

# API Call function
async def make_api_call(base64_image, prompt, schema, base_url, api_key):
    client = openai.AsyncClient(base_url= base_url, api_key=api_key)
    model_list = await client.models.list()
    model = model_list.data[0].id
    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "metadata_and_sample_data",
                "schema": schema.model_json_schema()
            },
        }
    )
    return completion.choices[0].message.content

# Batch processing function
async def process_images_in_batches(images, base_url, api_key):
    soil_data = []
    sample_data = []

    # Process images in batches of 10
    for i in range(0, len(images), 10):
        batch = images[i:i+10]
        
        # First API call for soil data (prompt_soil_data)
        soil_tasks = [make_api_call(image, prompt_soil_data, MetadataAndSoilData, base_url, api_key) for image in batch]
        soil_results = await asyncio.gather(*soil_tasks)
        soil_results = [json.loads(result) for result in soil_results]
        soil_data.extend(soil_results)
        
        # Second API call for sample data (prompt_sample_data)
        sample_tasks = [make_api_call(image, prompt_sample_data, MetadataAndSampleData, base_url, api_key) for image in batch]
        sample_results = await asyncio.gather(*sample_tasks)
        sample_results = [json.loads(result) for result in sample_results]
        sample_data.extend(sample_results)
        print(f"batch {i} done")

    return soil_data, sample_data

# Merge pages with same borehole
def merge_data(soil_data: List[dict], sample_data: List[dict], debug: bool = False):
    merged_soil_data = defaultdict(list)
    merged_sample_data = defaultdict(list)
    soil_metadata_map = {}
    sample_metadata_map = {}

    if debug:
        print("Starting merge_data function")
        print(f"Initial soil_data length: {len(soil_data)}")
        print(f"Initial sample_data length: {len(sample_data)}")

    # Merge the soil data based on HOLE_NO and store metadata
    for entry in soil_data:
        hole_no = entry['metadata']['HOLE_NO']
        merged_soil_data[hole_no].append(entry['soil_data'])
        if hole_no not in soil_metadata_map:
            soil_metadata_map[hole_no] = entry['metadata']
        if debug:
            print(f"Added soil_data for HOLE_NO: {hole_no}")

    # Merge the sample data based on HOLE_NO and store metadata
    for entry in sample_data:
        hole_no = entry['metadata']['HOLE_NO']
        merged_sample_data[hole_no].append(entry['sample_data'])
        if hole_no not in sample_metadata_map:
            sample_metadata_map[hole_no] = entry['metadata']
        if debug:
            print(f"Added sample_data for HOLE_NO: {hole_no}")

    final_merged_soil_data = []
    final_merged_sample_data = []

    # Merge soil data
    for hole_no, soil_entries in merged_soil_data.items():
        merged_soil = []
        for soil_list in soil_entries:
            merged_soil.extend(soil_list)
        final_merged_soil_data.append({
            'metadata': soil_metadata_map[hole_no],
            'soil_data': merged_soil
        })
        if debug:
            print(f"Merged soil_data for HOLE_NO: {hole_no}, total entries: {len(merged_soil)}")

    # Merge sample data
    for hole_no, sample_entries in merged_sample_data.items():
        all_samples = []
        for sample_list in sample_entries:
            all_samples.extend(sample_list)
        try:
            all_samples = sorted(all_samples, key=lambda x: int(x['Sample_number'][1:]))
        except Exception as e:
            if debug:
                print(f"Error sorting samples for HOLE_NO {hole_no}: {e}")
        final_merged_sample_data.append({
            'metadata': sample_metadata_map[hole_no],
            'sample_data': all_samples
        })
        if debug:
            print(f"Merged sample_data for HOLE_NO: {hole_no}, total entries: {len(all_samples)}")

    if debug:
        print("merge_data function completed")
        print(f"Final merged soil_data length: {len(final_merged_soil_data)}")
        print(f"Final merged sample_data length: {len(final_merged_sample_data)}")

    return final_merged_soil_data, final_merged_sample_data
# Function to extract the numeric values from the depth range string
def extract_depth_range(depth_range: str):
    # Remove trailing 'm' if present and strip spaces
    cleaned = depth_range.strip().rstrip('m').replace(' ', '')
    
    # Split by '~'
    if '~' in cleaned:
        parts = cleaned.split('~')
        try:
            min_depth = float(parts[0])
            max_depth = float(parts[1])
            return min_depth, max_depth
        except ValueError:
            return None, None  # Could not convert to float
    return None, None  # Invalid format
# Merge function that combines soil and sample data
def merge_soil_and_sample_data(soil_data, sample_data):

    # Create a dictionary to group samples by HOLE_NO for easy lookup
    sample_grouped_by_hole = {}
    for entry in sample_data:
        hole_no = entry['metadata']['HOLE_NO']
        if hole_no not in sample_grouped_by_hole:
            sample_grouped_by_hole[hole_no] = []
        sample_grouped_by_hole[hole_no].extend(entry['sample_data'])

    # Now we merge the sample data into the soil data
    merged_data = []

    for soil_entry in soil_data:
        hole_no = soil_entry['metadata']['HOLE_NO']
        soil_data = soil_entry['soil_data']

        # Get the corresponding samples for the current HOLE_NO
        samples_for_hole = sample_grouped_by_hole.get(hole_no, [])

        # Now we need to filter samples based on the soil depth_range
        for soil in soil_data:
            soil_depth_min, soil_depth_max = extract_depth_range(soil['depth_range'])

            # Filter samples that match the soil's depth range
            matching_samples = [
                sample for sample in samples_for_hole
                if soil_depth_min <= sample['Depth'] <= soil_depth_max
            ]

            # Add the matching samples to the soil data
            soil['samples'] = matching_samples

        merged_data.append({
            'metadata': soil_entry['metadata'],
            'soil_data': soil_data
        })

    return merged_data



