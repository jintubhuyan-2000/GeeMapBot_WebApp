import ee
import geemap
import ipywidgets as widgets
from ipyleaflet import DrawControl
from IPython.display import display, HTML, clear_output
from datetime import datetime
import ollama

# =============================================
# Earth Engine Authentication Setup
# =============================================
service_account = 'jintumonibhuyan@ee-jintumb6.iam.gserviceaccount.com'
json_key_path = "C:/Users/Admin/Downloads/ee-jintumb6-2b68bd3dbc74.json"

# =============================================
# UI Widgets Configuration
# =============================================
# Authentication Button
auth_button = widgets.Button(
    description="Authenticate Earth Engine",
    layout=widgets.Layout(width='250px', height='40px', border='2px solid #007BFF'),
    style={'button_color': '#007BFF', 'font_weight': 'bold', 'font_size': '14px'}
)

# Clear Login Button
clear_login_button = widgets.Button(
    description="Clear Login",
    layout=widgets.Layout(width='150px', height='35px', border='2px solid #DC3545'),
    style={'button_color': '#DC3545', 'font_weight': 'bold', 'font_size': '14px'}
)
clear_login_button.layout.display = 'none'

# =============================================
# Authentication Functions
# =============================================
def authenticate_earth_engine(b):
    """Handle Earth Engine authentication with service account"""
    try:
        credentials = ee.ServiceAccountCredentials(service_account, json_key_path)
        ee.Initialize(credentials)
        clear_output(wait=True)
        display(auth_button)
        
        success_html = """
        <div style="padding:10px; background-color:#D4EDDA; color:#155724; 
                    border-radius:5px; border:1px solid #C3E6CB;">
            <b>✅ Earth Engine authentication successful!</b>
        </div>
        """
        display(HTML(success_html))
        
        clear_login_button.layout.display = 'inline-block'
        display(clear_login_button)
        display_main_app()
        
    except Exception as e:
        error_html = f"""
        <div style="padding:10px; background-color:#F8D7DA; color:#721C24; 
                    border-radius:5px; border:1px solid #F5C6CB;">
            ❌ <b>Error during authentication:</b> {e}
        </div>
        """
        display(HTML(error_html))

def clear_login(b):
    """Reset authentication state"""
    clear_output(wait=True)
    display(auth_button)
    
    warning_html = """
    <div style="padding:10px; background-color:#FFF3CD; color:#856404; 
                border-radius:5px; border:1px solid #FFEEBA;">
        <b>⚠️ Earth Engine login cleared. Please re-authenticate.</b>
    </div>
    """
    display(HTML(warning_html))
    clear_login_button.layout.display = 'none'

# =============================================
# Main Application Components
# =============================================
def display_main_app():
    """Main application interface setup"""
    # Initialize Map
    Map = geemap.Map()
    Map.add_basemap("SATELLITE")
    
    # =========================================
    # Widget Configurations
    # =========================================
    # Satellite Selection
    satellite = widgets.Dropdown(
        options=['Landsat 8', 'Landsat 9', 'Sentinel-2'],
        value='Landsat 8',
        description='Satellite:'
    )
    
    # Date Controls
    start_date = widgets.DatePicker(description='Start Date:', value=datetime(2023, 1, 1))
    end_date = widgets.DatePicker(description='End Date:', value=datetime.today())
    cloud_cover = widgets.IntSlider(min=0, max=100, value=10, description='Cloud Cover %:')
    
    # Visualization Controls
    opacity = widgets.FloatSlider(min=0, max=1, value=1, step=0.1, description='Opacity:')
    gamma = widgets.FloatSlider(min=0.1, max=3, value=1, step=0.1, description='Gamma:')
    
    # Band Configuration
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
    
    # Band Selection Widgets
    band_vars = {name: widgets.Dropdown(description=f'{name} Band:') 
                 for name in ['NIR', 'RED', 'GREEN', 'BLUE']}
    
    # Index Calculation
    index_formula = widgets.Text(
        value='(NIR - RED)/(NIR + RED)',
        description='Index Formula:',
        placeholder='e.g., (B4 - B3)/(B4 + B3)'
    )
    
    # Drawing Control
    draw_control = DrawControl(position='topleft', draw_polygon=True, draw_rectangle=True)
    Map.add_control(draw_control)
    
    # Action Buttons
    load_button = widgets.Button(description="Load Imagery")
    calc_index_button = widgets.Button(description="Calculate Index")
    
    # Chat Interface
    chat_input = widgets.Text(description="Ask a question:", placeholder="Type your question here...")
    chat_output = widgets.Output()
    chat_button = widgets.Button(description="Ask")
    
    # =========================================
    # Application Logic
    # =========================================
    current_image = None  # Global variable for image storage
    
    def update_bands():
        """Update band options based on satellite selection"""
        config = band_config[satellite.value]
        for var in band_vars:
            band_vars[var].options = config['bands']
            band_vars[var].value = config['common'].get(var, config['bands'][0])
    
    def get_image():
        """Retrieve Earth Engine image based on current parameters"""
        if not draw_control.data:
            print("Error: Please draw a region of interest (ROI) on the map.")
            return None
        
        geometry = ee.Geometry(draw_control.data[-1]['geometry'])
        cloud_property = 'CLOUDY_PIXEL_PERCENTAGE' if satellite.value == 'Sentinel-2' else 'CLOUD_COVER'
        
        collection = ee.ImageCollection(band_config[satellite.value]['collection']) \
            .filterDate(start_date.value.strftime('%Y-%m-%d'), end_date.value.strftime('%Y-%m-%d')) \
            .filter(ee.Filter.lt(cloud_property, cloud_cover.value))
        
        return collection.median().clip(geometry)
    
    def on_load_button_clicked(b):
        """Handle image loading and display"""
        global current_image
        Map.layers = Map.layers[:2]  # Clear existing layers
        
        current_image = get_image()
        if current_image is None:
            return
        
        vis_params = {'opacity': opacity.value, 'gamma': gamma.value}
        Map.addLayer(current_image, vis_params, 'Main Image')
        Map.addLayer(current_image, {'bands': ['B4', 'B3', 'B2'], **vis_params}, 'RGB Composite')
        
        for band in band_config[satellite.value]['bands']:
            Map.addLayer(current_image, {'bands': [band], **vis_params}, f'Band {band}')
    
    def on_calc_index_clicked(b):
        """Handle custom index calculation"""
        global current_image
        if current_image is None:
            print("Error: No image loaded. Please load imagery first.")
            return
        
        try:
            formula = index_formula.value
            bands = {var: band_vars[var].value for var in band_vars}
            index = current_image.expression(formula, bands).rename('index')
            Map.addLayer(index, {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']}, 'Custom Index')
        except Exception as e:
            print(f"Error: {str(e)}")
    
    def on_chat_button_clicked(b):
        """Handle chat interactions"""
        global current_image
        question = chat_input.value
        if not question or not current_image:
            return
        
        try:
            response = ollama.chat(
                model="deepseek-r1:1.5b",
                messages=[{
                    "role": "user",
                    "content": f"Analyze this satellite data: {question}"
                }]
            )
            reply = response["message"]["content"]
            with chat_output:
                chat_output.clear_output()
                display(HTML(f"<div style='padding:10px'><b>Assistant:</b><br>{reply}</div>"))
        except Exception as e:
            print(f"Chat error: {str(e)}")
    
    # =========================================
    # UI Layout Assembly
    # =========================================
    update_bands()
    
    # Satellite Controls Group
    satellite_group = widgets.VBox([
        satellite,
        widgets.HBox([start_date, end_date]),
        cloud_cover
    ], layout=widgets.Layout(border='1px solid gray', padding='10px'))
    
    # Visualization Controls Group
    visualization_group = widgets.VBox([
        widgets.HBox([opacity, gamma]),
        index_formula,
        widgets.VBox(list(band_vars.values()))
    ], layout=widgets.Layout(border='1px solid gray', padding='10px'))
    
    # Chat Interface Group
    chat_group = widgets.VBox([
        chat_input,
        chat_button,
        chat_output
    ], layout=widgets.Layout(border='1px solid gray', padding='10px'))
    
    # Main Controls Assembly
    controls = widgets.VBox([
        satellite_group,
        visualization_group,
        widgets.HBox([load_button, calc_index_button]),
        chat_group
    ])
    
    # =========================================
    # Event Handlers Registration
    # =========================================
    auth_button.on_click(authenticate_earth_engine)
    clear_login_button.on_click(clear_login)
    load_button.on_click(on_load_button_clicked)
    calc_index_button.on_click(on_calc_index_clicked)
    chat_button.on_click(on_chat_button_clicked)
    satellite.observe(lambda _: update_bands(), 'value')
    
    # Display Components
    display(controls)
    display(Map)

# =============================================
# Initialization
# =============================================
if __name__ == "__main__":
    display(auth_button)