from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import os
import tempfile
import shutil
import asyncio
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import uuid
from urllib.parse import urlparse

from utils import (
    pdf_to_images,
    encode_image,
    process_images_in_batches,
    merge_data,
    merge_soil_and_sample_data
)
from pydantic_models import MetadataAndSoilData, MetadataAndSampleData

# Load environment variables
load_dotenv()
base_url = os.getenv("BASE_URL", "")
api_key = os.getenv("API_KEY", "")

# AWS S3 Configuration
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION", "us-east-1")

app = FastAPI(
    title="Drill Log Data Extraction API",
    description="Single endpoint API for extracting structured data from PDF drill logs stored in S3",
    version="1.0.0"
)

class ProcessRequest(BaseModel):
    s3_urls: List[str] = Field(..., description="List of S3 URLs pointing to PDF files")
    pdf_id: str = Field(..., description="Unique identifier for this PDF processing batch")
    user_id: str = Field(..., description="User identifier")

class BoreholeData(BaseModel):
    hole_no: str
    metadata: Dict[str, Any]
    sample_data: List[Dict[str, Any]]
    soil_data: List[Dict[str, Any]]
    source_pdf_url: str

class ProcessResponse(BaseModel):
    pdf_id: str
    user_id: str
    status: str
    total_pdfs_processed: int
    total_boreholes_found: int
    boreholes: List[BoreholeData]
    processing_summary: Dict[str, Any]

def create_s3_client():
    """Create and return S3 client"""
    return boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )

def parse_s3_url(s3_url: str) -> tuple:
    """Parse S3 URL to extract bucket and key"""
    parsed = urlparse(s3_url)
    if parsed.scheme != 's3':
        raise ValueError(f"Invalid S3 URL format: {s3_url}")
    
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    return bucket, key

async def download_pdf_from_s3(s3_url: str, local_path: str) -> bool:
    """Download PDF from S3 to local path"""
    try:
        s3_client = create_s3_client()
        bucket, key = parse_s3_url(s3_url)
        
        s3_client.download_file(bucket, key, local_path)
        return True
    except ClientError as e:
        print(f"Error downloading {s3_url}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error downloading {s3_url}: {e}")
        return False

async def process_single_pdf(s3_url: str, temp_dir: str) -> tuple:
    """Process a single PDF and return extracted data"""
    try:
        # Create filename from S3 URL
        filename = os.path.basename(urlparse(s3_url).path)
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
        pdf_path = os.path.join(temp_dir, filename)
        
        # Download PDF from S3
        success = await download_pdf_from_s3(s3_url, pdf_path)
        if not success:
            return None, f"Failed to download PDF from {s3_url}"
        
        # Create output directory for images
        output_dir = os.path.join(temp_dir, f"{filename}_images")
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert PDF to images
        pdf_to_images(pdf_path, output_dir, fixed_length=4000, max_workers=4)
        
        # Get image files
        image_files = sorted([
            os.path.join(output_dir, f) 
            for f in os.listdir(output_dir) 
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ])
        
        if not image_files:
            return None, f"No images could be extracted from {filename}"
        
        # Encode images to base64
        image_base64_list = [encode_image(image_path) for image_path in image_files]
        
        # Process images through the model
        soil_data, sample_data = await process_images_in_batches(
            image_base64_list, base_url, api_key
        )
        
        # Merge parsed data
        merged_soil_data, merged_sample_data = merge_data(soil_data, sample_data, debug=True)
        final_data = merge_soil_and_sample_data(merged_soil_data, merged_sample_data)
        
        return final_data, None
        
    except Exception as e:
        return None, f"Error processing {s3_url}: {str(e)}"

def organize_data_by_borehole(all_pdf_data: List[tuple]) -> List[BoreholeData]:
    """Organize extracted data by borehole across all PDFs"""
    boreholes = []
    
    for pdf_data, s3_url in all_pdf_data:
        if pdf_data is None:
            continue
            
        for item in pdf_data:
            hole_no = item['metadata'].get('HOLE_NO', 'UNKNOWN')
            
            borehole = BoreholeData(
                hole_no=hole_no,
                metadata=item['metadata'],
                sample_data=item.get('sample_data', []),
                soil_data=item.get('soil_data', []),
                source_pdf_url=s3_url
            )
            boreholes.append(borehole)
    
    return boreholes

@app.post("/api/v1/process-drill-logs", response_model=ProcessResponse)
async def process_drill_logs(request: ProcessRequest):
    """
    Process multiple PDF drill logs from S3 URLs and return organized borehole data.
    
    This endpoint:
    1. Downloads PDFs from provided S3 URLs
    2. Extracts structured data using Qwen2.5-VL-32B model
    3. Organizes data by borehole
    4. Returns comprehensive results for all boreholes found
    """
    
    if not request.s3_urls:
        raise HTTPException(status_code=400, detail="No S3 URLs provided")
    
    temp_dir = None
    
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"drill_logs_{request.pdf_id}_")
        
        # Process all PDFs concurrently
        tasks = []
        for s3_url in request.s3_urls:
            task = process_single_pdf(s3_url, temp_dir)
            tasks.append((task, s3_url))
        
        # Wait for all processing to complete
        results = []
        errors = []
        
        for task, s3_url in tasks:
            try:
                pdf_data, error = await task
                if error:
                    errors.append(f"{s3_url}: {error}")
                else:
                    results.append((pdf_data, s3_url))
            except Exception as e:
                errors.append(f"{s3_url}: {str(e)}")
        
        # Organize data by borehole
        boreholes = organize_data_by_borehole(results)
        
        # Create processing summary
        processing_summary = {
            "total_s3_urls": len(request.s3_urls),
            "successfully_processed": len(results),
            "failed_processing": len(errors),
            "errors": errors,
            "processing_time_info": "Completed using Qwen2.5-VL-32B two-step extraction"
        }
        
        return ProcessResponse(
            pdf_id=request.pdf_id,
            user_id=request.user_id,
            status="completed" if results else "failed",
            total_pdfs_processed=len(results),
            total_boreholes_found=len(boreholes),
            boreholes=boreholes,
            processing_summary=processing_summary
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Could not clean up temp directory {temp_dir}: {e}")

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Drill Log Data Extraction API",
        "version": "1.0.0",
        "model": "Qwen2.5-VL-32B-Instruct",
        "extraction_method": "Two-step schema extraction"
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Drill Log Data Extraction API",
        "version": "1.0.0",
        "endpoint": "/api/v1/process-drill-logs",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )