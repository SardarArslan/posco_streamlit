prompt_cls= """This image is part of a set of engineering documents. Based on its contents, classify it as either:
- "map" if it is a Boring Location Map (shows locations or layout)
- "table" if it is a Drill Log (shows tabular data about drilling)

Return just one word: "map" or "table"."""
prompt_table = """
You are an expert in korean and detecting table data:
Your are given an image of a borehole drill report, where the top section contain meta data informations like
PROJECT NAME
HOLE NO.
ELEV
LOCATION
GROUND WATER LEVEL
DATE
DRILLER

and below this metadata you will find a table, The left most column is showing a scale that represnt the depth of drill in meter.
The 3 columns from right most are telling information obout samplple colection, mainly sample number (s1, s2...etc), depth at with
sample is colected(in meter) and the collection method(represented by a symbol whose meaning is written in metadat section or sometimes written there, DO NOT PUT SYMBOL IN JSON )
in the middle part there is a column named (타격회수 관입량), that represent the number of hits (10/30, 20/40...etc) coresponding to
every sample

Similarly there are 3 more sub columns in column 현장 관찰기록, by name 토질명,색 조 and 관 찰. The 관 찰 contain the Depth range in start like 0.0~5.0m or 8.3~10.0m
these three columns contain information about soil for a given depth region
**Hits**: The number of hits recorded for the sample. IT IS ALSO CALLED "N VALUE" AND ALL THE ENTRIES IN THIS COLUMN ARE IN FORM OF FRACTION (e.g., 10/30, 20/40, etc.).
Now given an image with this table data your job is to return a json in below format
{
  metadata:{
    'PROJECT NAME':------,
    'HOLE NO.':---------,
    'ELEV':-----------,
    'LOCATION':--------,
    'GROUND WATER LEVEL':------,
    'DATE':---------
    'DRILLER':---------
  },
  sample_data:[
         {
          'sample_number':----,
          'Depth':----,
          'Hits':----,
          'Method':----
    },
        {
          'sample_number':----,
          'Depth':----,
          'Hits':----,
          'Method':----
    },

   ]
   soil_data:[
                    {
                    'depth_range':-----
                    'soil_name':----,
                    'soil_color':----,
                    'observation':----

                    },
                    {
                    'depth_range':-----
                    'soil_name':----,
                    'soil_color':----,
                    'observation':----

                    },

   ]
}
Please return Json only
"""

prompt_map = """
You are an expert in korean and detecting table data:
Your are given an image of a map, that has different locations of borehole. At those location you will see three thing a circular
symbol filled red and white, borehole name with number like BH-1, BH-2 etc.. and Below that you will see elevation, written as "EL:3.65", "EL:6.54" etc...
For every borehole, your job is to find 3 thing:
1. Borehole name... "BH-4"
2. Borehole number.  "4"
3. Elevation....."6.54"

Use different image processing to get it done:
Hint1 : ALl the information about a single borehole are written close to eachother
Now given an image with this map your job is to return a json in below format
{
  "metadata": [
    {
      "Name": "BH-1",
      "Number": 1,
      "Elevation": 100.5
    },
    {
      "Name": "BH-2",
      "Number": 2,
      "Elevation": 102.3
    },
    {
      "Name": "BH-3",
      "Number": 3,
      "Elevation": 99.8
    }
  ]
}

Please return Json only
"""

prompt_soil_data = """You are an expert in Korean and detecting table data. You are given an image of a borehole drill report, where the top section contains metadata information such as:
PROJECT NAME, HOLE NO., ELEV, LOCATION, GROUND WATER LEVEL, DATE, and DRILLER.

Below the metadata, you will find a table. The leftmost column represents the depth of the drill in meters. The rightmost three columns provide information about sample collection, such as sample number, depth of collection (in meters), and the collection method. However, DO NOT include any symbols in the collection method column.

There are also columns titled "타격회수" and "관입량", which represent the number of hits corresponding to the sample.

The focus of this task is to extract the **metadata** and **soil data** from the table. The soil data consists of:
1. **Depth Range**: The range of depth in meters (e.g., 0.0~5.0m).IT MUST BE IN THE FORM OF "0.0~5.0m" OR "5.0~7.0m" ETC.
2. **Soil Name**: The name of the soil.
3. **Soil Color**: The color of the soil.
4. **Observation**: Any additional observations or notes about the soil at that depth range.

Please return the data in JSON format as shown below:

{
  "metadata": {
    "PROJECT NAME": "--------",
    "HOLE NO.": "--------",
    "ELEV": "--------",
    "LOCATION": "--------",
    "GROUND WATER LEVEL": "--------",
    "DATE": "--------",
    "DRILLER": "--------"
  },
  "soil_data": [
    {
      "depth_range": "0.0~5.0m",
      "soil_name": "--------",
      "soil_color": "--------",
      "observation": "--------"
    },
    {
      "depth_range": "5.0~7.0m",
      "soil_name": "--------",
      "soil_color": "--------",
      "observation": "--------"
    },
    ...
  ]
}
Please return **only the JSON**.
"""
prompt_sample_data = """You are an expert in Korean and detecting table data. You are given an image of a borehole drill report, where the top section contains metadata information such as:
PROJECT NAME, HOLE NO., ELEV, LOCATION, GROUND WATER LEVEL, DATE, and DRILLER.

Below the metadata, you will find a table. The leftmost column represents the depth of the drill in meters. The rightmost three columns provide information about sample collection, such as sample number, depth of collection (in meters), and the collection method. However, DO NOT include any symbols in the collection method column.

There are also columns titled "타격회수" and "관입량", which represent the number of hits corresponding to the sample.

The focus of this task is to extract the **metadata** and **sample data** from the table. The sample data consists of:
1. **Sample Number**: The sample ID (e.g., S1, S2, etc.).
2. **Depth**: The depth at which the sample was collected (in meters).
3. **Hits**: The number of hits recorded for the sample. IT IS ALSO CALLED "N VALUE" AND ALL THE ENTRIES IN THIS COLUMN ARE IN FORM OF FRACTION (e.g., 10/30, 20/40, etc.).
4. **Method**: The method of sample collection, described in the metadata section (DO NOT include symbols).

Please return the data in JSON format as shown below:

{
  "metadata": {
    "PROJECT NAME": "--------",
    "HOLE NO.": "--------",
    "ELEV": "--------",
    "LOCATION": "--------",
    "GROUND WATER LEVEL": "--------",
    "DATE": "--------",
    "DRILLER": "--------"
  },
  "sample_data": [
    {
      "sample_number": "S1",
      "Depth": "5.0m",
      "Hits": "10/30",
      "Method": "----"
    },
    {
      "sample_number": "S2",
      "Depth": "7.0m",
      "Hits": "20/40",
      "Method": "----"
    },
    ...
  ]
}
Please return **only the JSON**.
"""