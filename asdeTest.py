import sys
import math
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog,QMessageBox, QAction
from PyQt5.QtGui import QPainter, QColor, QPen, QFont,QFontDatabase 
from PyQt5.QtCore import Qt, QPointF, QTimer
from collections import deque
from TraconSelection import TraconSelectionDialog
from geojsonLoader import GeoJsonLoader
from DataFetcher import DataFetcher
import os

class TRACONDisplay(QMainWindow):
    def __init__(self, tracon_config):
        super().__init__()

        self.setCursor(Qt.CrossCursor)

       # Load the font
        font_id = QFontDatabase.addApplicationFont("Resources/fonts/Roboto_Mono/RobotoMono-VariableFont_wght.ttf")
        if font_id == -1:
            print("Failed to load Roboto Mono font")
        else:
            print("Roboto Mono font loaded successfully")

        # Initial font size setup (10 is the default)
        self.starsFont = QFont("Roboto Mono", 10)
        

        # Set up menu bar
        self.menuBar = self.menuBar()

        # Font size menu
        font_menu = self.menuBar.addMenu("Font Size")

        # Define actions for different font sizes
        self.font_8_action = QAction("8", self)
        self.font_8_action.triggered.connect(lambda: self.set_font_size(8))

        self.font_10_action = QAction("10", self)
        self.font_10_action.triggered.connect(lambda: self.set_font_size(10))

        self.font_12_action = QAction("12", self)
        self.font_12_action.triggered.connect(lambda: self.set_font_size(12))

        self.font_14_action = QAction("14", self)
        self.font_14_action.triggered.connect(lambda: self.set_font_size(14))


        # Add actions to the font size menu
        font_menu.addAction(self.font_8_action)
        font_menu.addAction(self.font_10_action)
        font_menu.addAction(self.font_12_action)
        font_menu.addAction(self.font_14_action)

        # Load TRACON configuration from an external file
        self.tracon_config = self.load_tracon_config(tracon_config)

        self.aircraft_positions = {}  # Store positions for each aircraft

        # Get TRACON names from GeoJSON files in Resources directory
        tracon_names = self.get_tracon_names_from_geojson_files()
        dialog = TraconSelectionDialog(tracon_names)

        if dialog.exec_() == QDialog.Accepted:
            selected_tracon = dialog.get_selected_tracon()

            # Ensure the selected TRACON exists, otherwise use a default like 'C90'
            if selected_tracon in self.tracon_config:
                self.tracon_config = self.tracon_config[selected_tracon]
            else:
                print(f"Selected TRACON {selected_tracon} not found, using default.")
                self.tracon_config = self.tracon_config.get("C90", {})  # Use default config (C90) if not found
        else:
            print("No TRACON selected. Exiting...")
            sys.exit()

        # Initialize radar settings and center after TRACON selection
        self.radar_lat, self.radar_lon = self.tracon_config["radar_settings"]["lat_lon"]
        self.scale_factor = self.tracon_config["radar_settings"]["scale_factor"]


        # Initialize offset
        self.offset = QPointF(0, 0)  # Initialize the offset for dragging/zooming
        self.dragging = False
        

        # Set the radar center based on screen geometry
        screen_geometry = self.screen().geometry()
        screen_center = screen_geometry.center()
        self.radar_center = QPointF(screen_center.x(), screen_center.y())  # Initialize radar_center

        self.geojson_loader = GeoJsonLoader()
        self.load_geojson_data(self.tracon_config["geojson_file"])

        # Other initialization continues...

        self.aircraft_data = []
        # Remove the call to self.load_aircraft_data()

        # Initialize the selected TRACON's display
        version = "v0.0.0"
        self.setWindowTitle(f"RadarView {version} :: {self.tracon_config['tracon_name']}")
        self.showMaximized()

        # Load GeoJSON for the selected TRACON
        try:
            with open(self.tracon_config["geojson_file"], "r") as f:
                geojson_data = json.load(f)
                self.geojson_loader.load(geojson_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load GeoJSON file: {e}")

        # Data fetcher setup (use the correct lat, lon, and distance)
        self.data_fetcher = DataFetcher(self.radar_lat, self.radar_lon, dist=100)  # Example: 150 miles distance
        self.data_fetcher.data_fetched.connect(self.update_aircraft_data)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_fetching_data)
        self.timer.start(2000)  # Fetch data every 5 seconds

        print(f"TRACONDisplay initialized for {self.tracon_config['tracon_name']}.")


    def load_tracon_config(self, config_file):
        """Load TRACON configuration from an external JSON file."""
        try:
            with open(config_file, "r") as file:
                return json.load(file)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load TRACON configuration: {e}")
            sys.exit()

    def load_geojson_data(self, geojson_file):
        """Load GeoJSON data for the selected TRACON."""
        try:
            with open(geojson_file, "r") as file:
                geojson_data = json.load(file)
                self.geojson_loader.load(geojson_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load GeoJSON file: {e}")


    def get_tracon_names_from_geojson_files(self):
        """Retrieve available TRACON names from GeoJSON files."""
        tracon_names = []
        geojson_directory = r"Resources/tracons"
        
        for filename in os.listdir(geojson_directory):
            if filename.endswith(".geojson"):
                tracon_names.append(filename.replace(".geojson", ""))

        return tracon_names

    def draw_geojson_lines(self, painter):
        """Draw lines from the GeoJSON data with zoom and offset adjustments."""
        pen = QPen(QColor(0, 0, 0, 127))  # White lines with 50% transparency (alpha = 127)
        painter.setPen(pen)

        # Draw each line from the GeoJSON data
        for feature in self.geojson_loader.get_lines():
            coordinates = feature["geometry"]["coordinates"]
            for i in range(len(coordinates) - 1):
                # Map coordinates to radar coordinates and apply zoom/offset
                start_point = self.map_to_radar_coords(coordinates[i][1], coordinates[i][0])
                end_point = self.map_to_radar_coords(coordinates[i+1][1], coordinates[i+1][0])

                # If either of the points is out of bounds (0, 0), skip drawing
                if start_point == (0, 0) or end_point == (0, 0):
                    continue

                # Apply zoom and offset
                start_point = QPointF(self.radar_center.x() + start_point[0] * self.scale_factor + self.offset.x(),
                                    self.radar_center.y() - start_point[1] * self.scale_factor + self.offset.y())
                end_point = QPointF(self.radar_center.x() + end_point[0] * self.scale_factor + self.offset.x(),
                                    self.radar_center.y() - end_point[1] * self.scale_factor + self.offset.y())

                painter.drawLine(start_point, end_point)

    def start_fetching_data(self):
        if not self.data_fetcher.isRunning():
            self.data_fetcher.start()

    def update_aircraft_data(self, new_data):
        """Update the aircraft data and store positions for trails."""
        self.aircraft_data = new_data

        # Iterate over the new data
        for aircraft in new_data:
            aircraft_id = aircraft.get("flight", "N/A")
            lat = aircraft.get("lat")
            lon = aircraft.get("lon")

            # Ensure lat and lon are numeric
            try:
                lat = float(lat)
                lon = float(lon)
            except (ValueError, TypeError):
                print(f"ERROR: Non-numeric position data for aircraft {aircraft_id} (lat={lat}, lon={lon})")
                continue  # Skip this aircraft if conversion fails

            # Update position history if valid
            if aircraft_id not in self.aircraft_positions:
                self.aircraft_positions[aircraft_id] = deque(maxlen=8)  # Limit to last 8 positions
            self.aircraft_positions[aircraft_id].append((lat, lon))


        # Update radar display
        self.update()

    def set_font_size(self, size):
        """Set font size based on selected option."""
        self.starsFont.setPointSize(size)  # Update font size

        # Trigger a repaint to reflect font change
        self.update()

    def paintEvent(self, event):
        """Handle paint event to render radar, geoJSON, and aircraft trails."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(4,92,116))  # Black background

        # Apply updated font size before drawing
        painter.setFont(self.starsFont)  # Apply updated font

        self.draw_geojson_lines(painter)
        self.draw_aircraft(painter)



    def draw_aircraft(self, painter):
        for aircraft in self.aircraft_data:
            try:
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                alt = aircraft.get("alt", 0)  # Default to 0 if 'alt' is not provided
                callsign = aircraft.get("flight", "N/A")
                speed = aircraft.get('gs', 0)
                if speed != "N/A":
                    speed = int(speed)
                else:
                    speed = 0  # Default speed if 'gs' is unavailable or invalid
                track = aircraft.get("track", 0)  # Track angle in degrees

                if isinstance(speed, str) and speed.lower() == "ground":
                    continue  # Skip this aircraft

                # Skip aircraft if altitude is non-numeric or indicates 'ground'
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    x, y = self.map_to_radar_coords(lat, lon)

                # Convert altitude to integer
                alt = int(alt)

                # Skip aircraft above 18,000 feet
                if alt > 18000:
                    continue

                # Validate data
                if lat is None or lon is None:
                    continue

                # Map coordinates to radar screen
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # Calculate leader line endpoint
                leader_end_x = x  # Vertical line aligns with circle center
                leader_end_y = y - 20  # Adjust distance above the circle


                # Inside your drawing logic for aircraft, check if the aircraft is highlighted
                text_color = QColor(255, 255, 255)  # White color for non-highlighted aircraft

                painter.setFont(self.starsFont)  # Apply Roboto Mono font
                painter.setPen(text_color)

                # Draw the leader line

                painter.setPen(text_color)  # White leader line
                painter.drawLine(QPointF(x, y), QPointF(leader_end_x, leader_end_y))

                # Now draw the text with the appropriate color
                painter.setPen(text_color)
                painter.drawText(QPointF(leader_end_x + 5, leader_end_y - 5), callsign)
                painter.drawText(QPointF(leader_end_x + 5, leader_end_y + 10), f"{alt // 100:03} {speed}")


                circle_radius = 6
                painter.setBrush(QColor(31, 122, 255, 255))  # Blue color for aircraft
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    QPointF(x, y),
                    circle_radius,
                    circle_radius
                )

            except Exception as e:
                print(f"Error drawing aircraft: {e}")


  
    def map_to_radar_coords(self, lat, lon):
        """Map latitude and longitude to radar coordinates."""
        
        # Check if lat and lon are not sequences (lists or tuples)
        if isinstance(lat, (list, tuple)) or isinstance(lon, (list, tuple)):
            print(f"ERROR: lat or lon is a sequence (lat={lat}, lon={lon})")
            return 0, 0  # Return early if the values are invalid

        # Ensure lat and lon are floats
        lat = float(lat)
        lon = float(lon)

        # Calculate distance from radar center
        center_lat, center_lon = self.radar_lat, self.radar_lon
        distance = self.haversine(center_lat, center_lon, lat, lon)

        if distance > 200 * 1609.34:  # Ignore coordinates farther than 200 miles (in meters)
            return 0, 0  # Return a value outside the radar view

        scale = 800  # Adjust the scale for your coordinate system
        x = (lon - center_lon) * scale * math.cos(math.radians(center_lat))  # Adjust for latitude
        y = (lat - center_lat) * scale
        return x, y
    

    def haversine(self, lat1, lon1, lat2, lon2):
        """Calculate the distance in meters between two lat/lon points."""
        R = 6371000  # Radius of the Earth in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c  # Distance in meters
        return distance
    


    
    def mouseMoveEvent(self, event):
        """Handle mouse move event for dragging."""
        if self.dragging:
            delta = event.pos() - self.last_pos
            self.offset += delta
            self.last_pos = event.pos()
            self.update()


    def mouseReleaseEvent(self, event):
        """Handle mouse release event."""
        if event.button() == Qt.LeftButton:
            self.dragging = False

    def wheelEvent(self, event):
        """Zoom in or out on the display based on the mouse position."""
        zoom_in = event.angleDelta().y() > 0

        # Check if the CTRL key is held down
        ctrl_held = event.modifiers() & Qt.ControlModifier

        # Adjust zoom factor if CTRL is held down
        if ctrl_held:
            zoom_factor = 1.7 if zoom_in else 0.5  # Zoom twice as fast when CTRL is held
        else:
            zoom_factor = 1.1 if zoom_in else 0.9  # Regular zoom factor

        self.zoom_at(event.pos(), zoom_factor)

    def zoom_at(self, mouse_pos, zoom_factor):
        """Zoom based on the mouse position."""
        mouse_x = mouse_pos.x()
        mouse_y = mouse_pos.y()

        # Calculate the current mouse position in the radar's coordinate system
        mouse_radar_x = mouse_x - self.radar_center.x() - self.offset.x()
        mouse_radar_y = mouse_y - self.radar_center.y() - self.offset.y()

        # Apply the zoom factor
        self.scale_factor *= zoom_factor

        # Recalculate the offset based on the zoom center (mouse position)
        self.offset.setX(self.offset.x() - mouse_radar_x * (zoom_factor - 1))
        self.offset.setY(self.offset.y() - mouse_radar_y * (zoom_factor - 1))

        self.update()


    def mousePressEvent(self, event):
        """Handle mouse press event for dragging and CTRL+click interaction."""
        if event.button() == Qt.LeftButton:
            # Handle dragging
            self.last_pos = event.pos()
            self.dragging = True
        
        elif event.button() == Qt.LeftButton:
            self.update_display()

        # Handle CTRL + Click (Middle button click for aircraft selection)
        elif event.button() == Qt.MiddleButton:
            click_pos = event.pos()
            for aircraft in self.aircraft_data:
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # Check if click is within the circle's radius
                circle_radius = 15
                if (click_pos.x() - x) ** 2 + (click_pos.y() - y) ** 2 <= circle_radius ** 2:
                    # Toggle highlighted state
                    callsign = aircraft.get("flight")
                    if callsign:
                        aircraft["highlighted"] = not aircraft.get("highlighted", False)
                        self.highlighted_states[callsign] = aircraft["highlighted"]
                    self.update()  # Refresh the UI
                    break
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()



import requests
from PyQt5.QtCore import QThread, pyqtSignal

class DataFetcher(QThread):
    data_fetched = pyqtSignal(list)

    def __init__(self, lat, lon, dist):
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.dist = dist

    def run(self):
        aircraft_data = self.fetch_aircraft_data()
        self.data_fetched.emit(aircraft_data)

    def fetch_aircraft_data(self):
        url = f"https://api.adsb.lol/v2/lat/{self.lat}/lon/{self.lon}/dist/{self.dist}"
        try:
            print(f"Fetching data from {url}")  # Debug: Print URL
            response = requests.get(url)
            print(f"Response Status Code: {response.status_code}")  # Debug: Print status code

            if response.status_code == 200:
                data = response.json()  # Parse the JSON response
                #print(f"Fetched Data: {data}")  # Debug: Print the data received
                
                # Assuming the 'ac' key contains aircraft data
                aircraft_data = data.get("ac", [])
                if not aircraft_data:
                    print("No aircraft data available.")
                    return []
                
                # Map relevant fields to be used in the display
                parsed_data = []
                for ac in aircraft_data:
                    parsed_data.append({
                        'hex': ac.get('hex'),
                        'flight': ac.get('flight'),
                        'lat': ac.get('lat'),
                        'lon': ac.get('lon'),
                        'alt': ac.get('alt_baro'),  # Altitude in Barometric
                        'gs': ac.get('gs'),  # Ground speed
                        'track': ac.get('track'),
                        'mag_heading': ac.get('mag_heading'),
                        'emergency': ac.get('emergency'),
                        'type' : ac.get('t')
                    })
                    
                return parsed_data
            else:
                print(f"Error: Received status code {response.status_code}")  # Debug: Print error status code
                return []
        except Exception as e:
            print(f"Error fetching data: {e}")  # Debug: Print error
            return []
        
# GeoJson Loader to load GeoJSON data
class GeoJsonLoader:
    def __init__(self):
        self.geojson_data = {"type": "FeatureCollection", "features": []}

    def load(self, geojson_data):
        self.geojson_data = geojson_data
        # After loading the GeoJSON data
        #print("Loaded GeoJSON data:", geojson_data)


    def get_lines(self):
        return [
            feature for feature in self.geojson_data["features"]
            if feature["geometry"]["type"] == "LineString"
        ]



if __name__ == "__main__":
    app = QApplication(sys.argv)

    tracon_config_file = r"Resources/.AsdeConfig"

    # Initialize and show the TRACON display
    radar_display = TRACONDisplay(tracon_config_file)
    radar_display.show()

    sys.exit(app.exec_())
