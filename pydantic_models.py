from pydantic import BaseModel
from typing import List, Optional, Literal
# For map data extraction
class Borehole(BaseModel):
    Name: str
    Number: int
    Excavation_level: float
class Borehole_data(BaseModel):
    metadata: List[Borehole]
# For table data extraction
class Metadata(BaseModel):
    PROJECT_NAME: str
    HOLE_NO: str
    Excavation_level: float
    LOCATION: str
    GROUND_WATER_LEVEL: Optional[float]
    DATE: str
    DRILLER: str

class Sample(BaseModel):
    Sample_number: str
    Depth: float
    Hits: str
    Method: str

class MetadataAndSampleData(BaseModel):
    metadata: Metadata
    sample_data: List[Sample]

class Soil(BaseModel):
    depth_range: str
    soil_name: str
    soil_color: str
    observation: str

class MetadataAndSoilData(BaseModel):
    metadata: Metadata
    soil_data: List[Soil]