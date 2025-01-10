import sys
import requests
import math
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QVBoxLayout, QComboBox, QPushButton, QLabel, QMessageBox, QWidget, QHBoxLayout
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QFontDatabase
from PyQt5.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal
import os
from collections import deque

class TraconSelectionDialog(QDialog):
    def __init__(self, tracon_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select TRACON")

        # Set the window size and make it center-aligned
        self.setFixedSize(1000, 800)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)  # No borders
        self.pixmap = QPixmap('C:/Users/abbym/Documents/RadarView/Resources/pics/launch-background.png')



        # Main layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)  # Center the entire layout

        # Centered container for the selection box
        container = QWidget(self)
        container.setStyleSheet("background-color: rgba(61, 61, 61, 0.8); border-radius: 10px; padding: 20px;")
        container_layout = QVBoxLayout(container)

        # Label with sleek modern style
        self.label = QLabel("Select a TRACON to load:", container)
        container_layout.addWidget(self.label)

        self.label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #E1E1E1;
            margin-bottom: 20px;
            text-align: center;
        """)

        # ComboBox for TRACON names
        self.comboBox = QComboBox(container)
        self.comboBox.addItems(tracon_names)
        container_layout.addWidget(self.comboBox)

        # Style the comboBox with smooth edges and modern font
        self.comboBox.setStyleSheet("""
            QComboBox {
                background-color: #4C4C4C;
                font-size: 16px;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #888;
                color: #E1E1E1;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: #E1E1E1;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #555;
            }
        """)

        # Create buttons layout
        button_layout = QHBoxLayout()
        container_layout.addLayout(button_layout)

        # OK Button
        self.ok_button = QPushButton("OK", container)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color:rgb(0, 0, 0);
                color: white;
                font-size: 16px;
                padding: 12px 30px;
                border-radius: 8px;
                border: none;

            }
            QPushButton:hover {
                background-color:rgb(255, 255, 255);
                color: black;

            }
        """)

        # Cancel Button
        self.cancel_button = QPushButton("Cancel", container)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color:rgb(134, 134, 134);
                color: white;
                font-size: 16px;
                padding: 12px 30px;
                border-radius: 8px;
                border: none;
            }
        """)

        layout.addWidget(container)  # Add the container with all elements to the main layout

    def get_selected_tracon(self):
        """Return the selected TRACON name."""
        return self.comboBox.currentText()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)  # Draw the background image
        super().paintEvent(event)



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
        self.starsFont = QFont("Roboto Mono", 10)  # Font size 10

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
        self.highlighted_states = {}        
        # Remove the call to self.load_aircraft_data()

        # Initialize the selected TRACON's display
        version = "v1.1.0"
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
        geojson_directory = "Resources"
        
        for filename in os.listdir(geojson_directory):
            if filename.endswith(".geojson"):
                tracon_names.append(filename.replace(".geojson", ""))

        return tracon_names

    def draw_geojson_lines(self, painter):
        """Draw lines from the GeoJSON data with zoom and offset adjustments."""
        pen = QPen(QColor(255, 255, 255, 127))  # White lines with 50% transparency (alpha = 127)
        pen.setWidth(1)
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

    """def update_aircraft_data(self, new_data):
        #print(f"Updating aircraft data with {len(data)} entries.")  # Debug statement
        self.aircraft_data = new_data

        # Store the positions in aircraft_positions (keep only the last 8 positions)
        for aircraft in new_data:
            aircraft_id = aircraft.get("flight", "N/A")
            lat = aircraft.get("lat")
            lon = aircraft.get("lon")

            # Debugging to check types of lat and lon
            #print(f"Aircraft {aircraft_id}: lat={lat} (type: {type(lat)}), lon={lon} (type: {type(lon)})")
        for aircraft in self.aircraft_data:
            callsign = aircraft.get("flight")
            if callsign:
                self.highlighted_states[callsign] = aircraft.get("highlighted", False)

                # Update aircraft_data
                self.aircraft_data = new_data

                # Restore highlighted states
            for aircraft in self.aircraft_data:
                callsign = aircraft.get("flight")
                if callsign and callsign in self.highlighted_states:
                    aircraft["highlighted"] = self.highlighted_states[callsign]


            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                if aircraft_id not in self.aircraft_positions:
                    self.aircraft_positions[aircraft_id] = deque(maxlen=8)  # Limit to last 8 positions
                    # Append the new position to the deque
                    self.aircraft_positions[aircraft_id].append((lat, lon))
                else:
                    print(f"ERROR: Invalid position data for aircraft {aircraft_id} (lat={lat}, lon={lon})")

            self.update()"""

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

            # Restore highlighted state
            highlighted = self.highlighted_states.get(aircraft_id, False)
            aircraft["highlighted"] = highlighted

        # Update radar display
        self.update()

    


    def paintEvent(self, event):
        """Handle paint event to render radar, geoJSON, and aircraft trails."""
        print("Painting radar display...")  # Debug statement
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))  # Black background
        self.draw_geojson_lines(painter)
        self.draw_radar(painter)
        self.draw_aircraft(painter)


    def draw_radar(self, painter):
        pen = QPen(QColor(200, 200, 200))  # Grey-white rings
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 10):
            painter.drawEllipse(self.radar_center + self.offset, i * 80 * self.scale_factor, i * 80 * self.scale_factor)


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

                # Draw aircraft trail
                self.draw_aircraft_trail(aircraft, painter)

                # Map coordinates to radar screen
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # **Prediction Logic:**
                # Calculate the predicted position in 1 minute
                predicted_lat, predicted_lon = self.predict_position(lat, lon, track, speed)

                # Map predicted coordinates to radar screen
                predicted_x, predicted_y = self.map_to_radar_coords(predicted_lat, predicted_lon)
                predicted_x = self.radar_center.x() + (predicted_x * self.scale_factor) + self.offset.x()
                predicted_y = self.radar_center.y() - (predicted_y * self.scale_factor) + self.offset.y()


                # Calculate leader line endpoint
                leader_end_x = x  # Vertical line aligns with circle center
                leader_end_y = y - 20  # Adjust distance above the circle


                # Inside your drawing logic for aircraft, check if the aircraft is highlighted
                highlighted = aircraft.get("highlighted", False)

                # If highlighted, use a different text color
                if highlighted:
                    text_color = QColor(10,186,187)  # Blue color for highlighted aircraft
                else:
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



                # Draw the line from the blue aircraft dot to the predicted position
                painter.setPen(QPen(QColor(255, 255, 255), 1))  # White line with thickness 1
                painter.drawLine(QPointF(x, y), QPointF(predicted_x, predicted_y))  # Line from aircraft to predicted position

                circle_radius = 5
                painter.setBrush(QColor(31, 122, 255, 255))  # Blue color for aircraft
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    QPointF(x, y),
                    circle_radius,
                    circle_radius
                )




            except Exception as e:
                print(f"Error drawing aircraft: {e}")

    """def draw_aircraft(self, painter):
        for aircraft in self.aircraft_data:
            try:
                # Safely extract latitude and longitude
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                callsign = aircraft.get("flight", "N/A")
                alt = aircraft.get("alt", 0)  # Default to 0 if missing
                speed = aircraft.get("gs", 0)  # Ground speed
                track = aircraft.get("track", 0)  # Track angle in degrees

                # Ensure latitude and longitude are valid
                if lat is None or lon is None or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    print(f"Skipping {callsign}: Invalid coordinates lat={lat}, lon={lon}")
                    continue

                # Safely parse altitude and speed
                try:
                    alt = int(alt)  # Convert altitude to integer
                except ValueError:
                    print(f"Skipping {callsign}: Invalid altitude alt={alt}")
                    continue

                try:
                    speed = int(speed)  # Convert speed to integer
                except ValueError:
                    print(f"Skipping {callsign}: Invalid speed gs={speed}")
                    speed = 0  # Default to 0 if invalid

                # Skip aircraft above 18,000 feet
                if alt > 18000:
                    print(f"Skipping {callsign}: Altitude above 18,000 ft (alt={alt})")
                    continue

                # Map coordinates to radar screen
                x, y = self.map_to_radar_coords(lat, lon)
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # Draw the aircraft on the radar
                circle_radius = 5
                painter.setBrush(QColor(31, 122, 255, 255))  # Blue aircraft marker
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)

                # Draw the aircraft's trail
                self.draw_aircraft_trail(aircraft, painter)

            except Exception as e:
                print(f"Error drawing aircraft {aircraft.get('flight', 'Unknown')}: {e}")"""


                
    def predict_position(self, lat, lon, track, speed):
        """Predict the position of the aircraft in 1 minute."""
        # Convert speed from knots to meters per second (1 knot = 0.514444 m/s)
        speed_mps = speed * 0.514444

        # Distance traveled in 1 minute
        distance = speed_mps * 60  # meters

        # Convert track to radians (track is given in degrees)
        track_rad = math.radians(track)

        # Calculate change in latitude and longitude
        delta_lat = distance * math.cos(track_rad) / 111320  # 1 degree of latitude is ~111320 meters
        delta_lon = distance * math.sin(track_rad) / (40008000 / 360) * math.cos(math.radians(lat))  # Degree length varies with latitude

        # Calculate new latitude and longitude
        predicted_lat = lat + delta_lat
        predicted_lon = lon + delta_lon

        return predicted_lat, predicted_lon



    def draw_aircraft_trail(self, aircraft, painter):
        """Draw the trail for the aircraft."""
        aircraft_id = aircraft.get("flight", "N/A")
        if aircraft_id not in self.aircraft_positions:
            return

        # Get the last positions of the aircraft in reverse order (newest first)
        positions = list(self.aircraft_positions[aircraft_id])[::-1]

        # Draw circles for the trail
        for i, (lat, lon) in enumerate(positions):
            # Map the coordinates to radar screen
            x, y = self.map_to_radar_coords(lat, lon)
            x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
            y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

            # Adjust color intensity for fading effect
            # The first circle is fully blue, and the color fades with each older position
            alpha_value = max(255 - i * 30, 50)  # Fade effect, stops at a certain opacity
            color = QColor(27,110,224, alpha_value)  # Blue with fading alpha

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)

            # Draw the trail circle
            painter.drawEllipse(QPointF(x, y), 4, 4)  # Smaller circles for the trail

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


        
    def assign_sector(self, lat, lon, alt):
        """Assign aircraft to a TRACON sector based on position or altitude."""
        if alt < 10000:
            return "F"
        elif 10000 <= alt < 20000:
            return "V"
        elif 20000 <= alt < 30000:
            return "A"
        else:
            return "H"


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
        if zoom_in:
            self.zoom_at(event.pos(), zoom_in)
        else:
            self.zoom_at(event.pos(), zoom_in)

    def zoom_at(self, mouse_pos, zoom_in):
        """Zoom based on the mouse position."""
        mouse_x = mouse_pos.x()
        mouse_y = mouse_pos.y()

        # Calculate the current mouse position in the radar's coordinate system
        mouse_radar_x = mouse_x - self.radar_center.x() - self.offset.x()
        mouse_radar_y = mouse_y - self.radar_center.y() - self.offset.y()

        # Determine zoom factor
        zoom_factor = 1.1 if zoom_in else 0.9
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
                        'emergency': ac.get('emergency'),
                    })
                    
                return parsed_data
            else:
                print(f"Error: Received status code {response.status_code}")  # Debug: Print error status code
                return []
        except Exception as e:
            print(f"Error fetching data: {e}")  # Debug: Print error
            return []

if __name__ == "__main__":
    app = QApplication(sys.argv)



    tracon_config_file = "resources/TraconConfig.json"



    # Initialize and show the TRACON display
    radar_display = TRACONDisplay(tracon_config_file)
    radar_display.show()

    sys.exit(app.exec_())
