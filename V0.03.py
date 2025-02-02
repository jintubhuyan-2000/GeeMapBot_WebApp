import ee
import geemap
import ipywidgets as widgets
from ipyleaflet import DrawControl
from IPython.display import display, HTML
from datetime import datetime
import ollama

# Initialize Earth Engine
ee.Authenticate()
ee.Initialize()

# Create Map
Map = geemap.Map()
Map.add_basemap("SATELLITE")

# Widgets
satellite = widgets.Dropdown(
    options=['Landsat 8', 'Landsat 9', 'Sentinel-2'],
    value='Landsat 8',
    description='Satellite:'
)

start_date = widgets.DatePicker(description='Start Date:', value=datetime(2023, 1, 1))
end_date = widgets.DatePicker(description='End Date:', value=datetime.today())
cloud_cover = widgets.IntSlider(min=0, max=100, value=10, description='Cloud Cover %:')

draw_control = DrawControl(position='topleft', draw_polygon=True, draw_rectangle=True)
Map.add_control(draw_control)

# Visualization controls
opacity = widgets.FloatSlider(min=0, max=1, value=1, step=0.1, description='Opacity:')
gamma = widgets.FloatSlider(min=0.1, max=3, value=1, step=0.1, description='Gamma:')

# Index calculation
index_formula = widgets.Text(
    value='(NIR - RED)/(NIR + RED)',
    description='Index Formula:',
    placeholder='e.g., (B4 - B3)/(B4 + B3)'
)

band_config = {
    'Landsat 8': {
        'collection': "LANDSAT/LC08/C02/T1",
        'bands': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'common': {'BLUE': 'B2', 'GREEN': 'B3', 'RED': 'B4', 'NIR': 'B5'}
    },
    'Landsat 9': {
        'collection': 'LANDSAT/LC09/C02/T1',
        'bands': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7'],
        'common': {'BLUE': 'B2', 'GREEN': 'B3', 'RED': 'B4', 'NIR': 'B5'}
    },
    'Sentinel-2': {
        'collection': 'COPERNICUS/S2_SR_HARMONIZED',
        'bands': ['B2', 'B3', 'B4', 'B8', 'B11', 'B12'],
        'common': {'BLUE': 'B2', 'GREEN': 'B3', 'RED': 'B4', 'NIR': 'B8'}
    }
}

band_vars = {
    name: widgets.Dropdown(description=f'{name} Band:') 
    for name in ['NIR', 'RED', 'GREEN', 'BLUE']
}

# Global variable to store the Earth Engine image
current_image = None

# Chatbot widgets
chat_input = widgets.Text(description="Ask a question:", placeholder="Type your question here...")
chat_output = widgets.Output()
chat_button = widgets.Button(description="Ask")

def update_bands():
    config = band_config[satellite.value]
    for var in band_vars:
        band_vars[var].options = config['bands']
        band_vars[var].value = config['common'].get(var, config['bands'][0])

update_bands()

load_button = widgets.Button(description="Load Imagery")
calc_index_button = widgets.Button(description="Calculate Index")

def get_image():
    if not draw_control.data:
        print("Error: Please draw a region of interest (ROI) on the map.")
        return None
    
    geometry = ee.Geometry(draw_control.data[-1]['geometry'])
    
    # Determine the cloud cover property based on the satellite
    cloud_property = 'CLOUDY_PIXEL_PERCENTAGE' if satellite.value == 'Sentinel-2' else 'CLOUD_COVER'
    
    collection = ee.ImageCollection(band_config[satellite.value]['collection']) \
        .filterDate(start_date.value.strftime('%Y-%m-%d'), end_date.value.strftime('%Y-%m-%d')) \
        .filter(ee.Filter.lt(cloud_property, cloud_cover.value))
    
    image = collection.median()
    
    # Clip the image if geometry is provided
    if geometry:
        image = image.clip(geometry)
    
    return image

def on_load_button_clicked(b):
    global current_image
    Map.layers = Map.layers[:2]  # Clear existing layers except the basemap
    
    current_image = get_image()
    if current_image is None:
        return
    
    # Add main image with all bands
    vis_params = {'opacity': opacity.value, 'gamma': gamma.value}
    Map.addLayer(current_image, vis_params, 'Main Image')
    
    # Add RGB composite
    rgb_bands = ['B4', 'B3', 'B2']  # Same for Landsat and Sentinel-2
    Map.addLayer(current_image, {'bands': rgb_bands, **vis_params}, 'RGB Composite')
    
    # Add individual band layers
    for band in band_config[satellite.value]['bands']:
        Map.addLayer(current_image, {'bands': [band], **vis_params}, f'Band {band}')

def on_calc_index_clicked(b):
    global current_image
    if current_image is None:
        print("Error: No image loaded. Please load imagery first.")
        return
    
    formula = index_formula.value
    bands = {var: band_vars[var].value for var in band_vars}
    
    try:
        index = current_image.expression(formula, bands).rename('index')
        Map.addLayer(index, {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']}, 'Custom Index')
    except ee.EEException as e:
        print(f"Earth Engine Error: {str(e)}")
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")

def extract_image_info(image, geometry):
    """Extract detailed information about the image."""
    if image is None:
        return "No image loaded."
    
    # Get image properties
    info = {
        'Bands': image.bandNames().getInfo(),
        'Pixel Count': image.reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=geometry,
            scale=30  # Adjust scale based on satellite
        ).getInfo(),
        'Mean Pixel Values': image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=30
        ).getInfo(),
        'NDVI': image.normalizedDifference(['B5', 'B4']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=30
        ).getInfo(),
        'Boundary Extension': geometry.bounds().getInfo() if geometry else "Not defined",
        'Band Values': {}
    }
    # Extract band values for each pixel
    #for band in image.bandNames().getInfo():
    #    band_values = image.select(band).reduceRegion(
    #        reducer=ee.Reducer.toList(),
    #        geometry=geometry,
    #        scale=30
    #    ).getInfo()
    #   info['Band Values'][band] = band_values.get(band, [])
    
    
    return info

from IPython.display import HTML, display

def on_chat_button_clicked(b):
    global current_image
    question = chat_input.value
    if not question:
        return

    # Extract detailed image information
    geometry = ee.Geometry(draw_control.data[-1]['geometry']) if draw_control.data else None
    image_info = extract_image_info(current_image, geometry)
    
    # Construct the context for DeepSeek
    context = f"""
        You are a helpful assistant for Earth Engine data analysis. Your task is to analyze satellite imagery data and provide insights based on the following information:

        ### Satellite and Data Details:
        - **Satellite Name**: {satellite.value}
        - **Date Range**: {start_date.value.strftime('%Y-%m-%d')} to {end_date.value.strftime('%Y-%m-%d')}
        - **Cloud Cover**: {cloud_cover.value}%
        - **Region of Interest (ROI)**: {"Defined" if draw_control.data else "Not defined"}
        - **Current Image Status**: {"Loaded" if current_image else "Not loaded"}

        ### Image Information:
        - **Bands Available**: {image_info.get('Bands', 'N/A')}
        - **Pixel Count**: {image_info.get('Pixel Count', 'N/A')}
        - **Mean Pixel Values**: {image_info.get('Mean Pixel Values', 'N/A')}
        - **NDVI**: {image_info.get('NDVI', 'N/A')}
        - **Boundary Extension**: {image_info.get('Boundary Extension', 'N/A')}
        - **Band Values**: {image_info.get('Band Values', 'N/A')}

        ### Additional Context:
        - The data is sourced from Google Earth Engine (GEE) using the GEE Python API.
        - The user has drawn a region of interest (ROI) on the map and loaded the satellite imagery.
        - The user is interested in analyzing the data and answering questions related to the imagery, such as vegetation health, water bodies, urban development, or custom indices.

        ### User's Question:
        The user has asked the following question: "{question}"

        ### Instructions for DeepSeek:
        1. Analyze the provided data and answer the user's question in detail.
        2. If the question involves calculating indices (e.g., NDVI, NDWI, EVI), use the formula provided by the user or suggest an appropriate formula.
        3. Provide recommendations or insights based on the analysis (e.g., vegetation health, water body detection, urban development).
        4. If additional information or clarification is needed, ask the user for further details.
    """

    # Combine the context and the user's question
    full_message = f"{context}\n\nPlease analyze the data and provide a detailed response to the user's question."

    # Send the combined message to the chatbot model
    response = ollama.chat(
        model="deepseek-r1:1.5b",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": full_message}
        ]
    )
    
    # Extract the reply from the response
    reply = response["message"]["content"]

    # Format the reply with HTML for better readability
    formatted_reply = f"""
    <div style="font-family: Arial, sans-serif; padding: 10px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
        <b>GeeMapBot:</b>
        <p style="white-space: pre-wrap;">{reply}</p>
    </div>
    """

    # Display the formatted reply in the chat output
    with chat_output:
        chat_output.clear_output()
        display(HTML(formatted_reply))

# Attach event handlers
load_button.on_click(on_load_button_clicked)
calc_index_button.on_click(on_calc_index_clicked)
chat_button.on_click(on_chat_button_clicked)
satellite.observe(lambda _: update_bands(), 'value')

# Layout
satellite_group = widgets.VBox([
    satellite,
    widgets.HBox([start_date, end_date]),
    cloud_cover
], layout=widgets.Layout(border='1px solid gray', padding='10px'))

visualization_group = widgets.VBox([
    widgets.HBox([opacity, gamma]),
    index_formula,
    widgets.VBox(list(band_vars.values()))
], layout=widgets.Layout(border='1px solid gray', padding='10px'))

buttons_group = widgets.HBox([load_button, calc_index_button])

chat_group = widgets.VBox([
    chat_input,
    chat_button,
    chat_output
], layout=widgets.Layout(border='1px solid gray', padding='10px'))

controls = widgets.VBox([
    satellite_group,
    visualization_group,
    buttons_group,
    chat_group
])

display(controls)
Map