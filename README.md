# Geotechnical Report Analysis Agent

The **Geotechnical Report Analysis Agent** is a Streamlit-based web application designed to help users analyze geotechnical reports in PDF format. The application extracts data from PDF reports, processes it, and provides a visual representation of the data by displaying buttons for different boreholes. Upon clicking a borehole button, users can view the corresponding merged JSON data for soil and sample details.

## Features

- **PDF Upload**: Upload a geotechnical PDF file to begin processing.
- **PDF to Image Conversion**: Convert PDF pages into images for further processing.
- **Asynchronous Image Processing**: Process images in batches to extract soil and sample data asynchronously.
- **Data Merging**: Merge soil and sample data based on the borehole (`HOLE_NO`) and display the results in an organized format.
- **Interactive User Interface**: Display buttons for each `HOLE_NO` where users can click to view the corresponding data in JSON format.

## Requirements

To run this application, ensure that you have the following dependencies installed:

- Python 3.7+
- Streamlit
- Pydantic
- OpenAI
- Other dependencies are listed in `requirements.txt`

## Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/llm-team-org/posco-streamlit.git
   cd posco-streamlit
