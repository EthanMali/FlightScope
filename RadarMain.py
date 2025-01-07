import sys
import requests
import math
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QVBoxLayout, QComboBox, QPushButton, QLabel, QMessageBox, QFileDialog
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt5.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QRectF
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager
import os
from collections import deque


# Dialog to select TRACON
class TraconSelectionDialog(QDialog):
    def __init__(self, tracon_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select TRACON")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout(self)

        self.label = QLabel("Select a TRACON to load:", self)
        layout.addWidget(self.label)
        
        self.comboBox = QComboBox(self)
        self.comboBox.addItems(tracon_names)  # Add TRACON names to the combo box
        layout.addWidget(self.comboBox)
        
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
    
    def get_selected_tracon(self):
        """Return the selected TRACON name."""
        return self.comboBox.currentText()

# GeoJson Loader to load GeoJSON data
class GeoJsonLoader:
    def __init__(self):
        self.geojson_data = {"type": "FeatureCollection", "features": []}

    def load(self, geojson_data):
        self.geojson_data = geojson_data
        # After loading the GeoJSON data
        print("Loaded GeoJSON data:", geojson_data)


    def get_lines(self):
        return [
            feature for feature in self.geojson_data["features"]
            if feature["geometry"]["type"] == "LineString"
        ]

class TRACONDisplay(QMainWindow):
    def __init__(self, tracon_config):
        super().__init__()

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

        # Set the radar center based on screen geometry
        screen_geometry = self.screen().geometry()
        screen_center = screen_geometry.center()
        self.radar_center = QPointF(screen_center.x(), screen_center.y())  # Initialize radar_center

        self.geojson_loader = GeoJsonLoader()
        self.load_geojson_data(self.tracon_config["geojson_file"])

        # Other initialization continues...

        self.aircraft_data = []  # Placeholder for aircraft data
        
        # Remove the call to self.load_aircraft_data()

        # Initialize the selected TRACON's display
        self.setWindowTitle(self.tracon_config["tracon_name"])
        self.showMaximized()

        # Load GeoJSON for the selected TRACON
        try:
            with open(self.tracon_config["geojson_file"], "r") as f:
                geojson_data = json.load(f)
                self.geojson_loader.load(geojson_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load GeoJSON file: {e}")

        # Data fetcher setup (use the correct lat, lon, and distance)
        self.data_fetcher = DataFetcher(self.radar_lat, self.radar_lon, dist=150)  # Example: 150 miles distance
        self.data_fetcher.data_fetched.connect(self.update_aircraft_data)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_fetching_data)
        self.timer.start(5000)  # Fetch data every 5 seconds

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


    def update_aircraft_data(self, data):
        """Update the aircraft data and store their positions."""
        print(f"Updating aircraft data with {len(data)} entries.")  # Debug statement
        self.aircraft_data = data

        # Store the positions in aircraft_positions (keep only the last 8 positions)
        for aircraft in data:
            aircraft_id = aircraft.get("flight", "N/A")
            lat = aircraft.get("lat")
            lon = aircraft.get("lon")

            if aircraft_id not in self.aircraft_positions:
                self.aircraft_positions[aircraft_id] = deque(maxlen=8)  # Limit to the last 8 positions

            # Append the new position to the queue
            if lat is not None and lon is not None:
                self.aircraft_positions[aircraft_id].append((lat, lon))

        self.update()  # Trigger a repaint to draw the new aircraft data and trails


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
        """Draw the aircraft and its trail on the radar using QPainter."""
        for aircraft in self.aircraft_data:
            try:
                lat = aircraft.get("lat")
                lon = aircraft.get("lon")
                alt = aircraft.get("alt", 0)  # Default to 0 if 'alt' is not provided
                callsign = aircraft.get("flight", "N/A")
                speed = f"{int(aircraft.get('gs', 0))}" if aircraft.get("gs") else "N/A"

                # Skip aircraft if altitude is non-numeric or indicates 'ground'
                if not isinstance(alt, (int, float)) and not alt.isdigit():
                    continue

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

                # Draw the aircraft as a blue circle
                circle_radius = 5
                painter.setBrush(QColor(31,122,255,255))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    QPointF(x, y),
                    circle_radius,
                    circle_radius
                )

                # Draw altitude and speed near the aircraft
                painter.setPen(Qt.white)
                painter.drawText(QPointF(x + 10, y - 10), callsign)
                painter.drawText(QPointF(x + 10, y + 5), f"{alt // 100:03} {speed}")
            except Exception as e:
                print(f"Error drawing aircraft: {e}")


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
        # Get the radar center from the current TRACON config
        center_lat, center_lon = self.radar_lat, self.radar_lon

        # Calculate distance from radar center
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
    
    def mousePressEvent(self, event):
        """Handle mouse press event for dragging."""
        if event.button() == Qt.LeftButton:
            self.last_pos = event.pos()
            self.dragging = True

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
                print(f"Fetched Data: {data}")  # Debug: Print the data received
                
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
