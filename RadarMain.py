import sys
import requests
import math
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenuBar, QMenu, QAction, QFileDialog
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal, QRectF
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager

class DataFetcher(QThread):
    data_fetched = pyqtSignal(list)

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        """Fetch aircraft data in a separate thread."""
        url = "https://opensky-network.org/api/states/all"
        params = {"lamin": 41.975710, "lomin": -87.903006, "lamax": 41.975710, "lomax": -87.903006}
        try:
            print("Fetching data from OpenSky API...")
            response = requests.get(url, params=params, auth=(self.username, self.password))
            response.raise_for_status()
            data = response.json()
            aircraft_data = [
                self.enrich_aircraft_data(state)
                for state in data.get("states", [])
                if state[7] and state[7] > 500  # Exclude ground
            ]
            print(f"Fetched {len(aircraft_data)} aircraft.")
            self.data_fetched.emit(aircraft_data)
        except requests.RequestException as e:
            print(f"Error fetching aircraft data: {e}")
            self.data_fetched.emit([])

    def enrich_aircraft_data(self, state):
        """Enrich data without aircraft type and destination."""
        state.append("Unknown")  # Placeholder for destination
        state.append("Unknown")  # Placeholder for aircraft type
        return state
    

class GeoJsonLoader:
    def __init__(self):
        self.geojson_data = {"type": "FeatureCollection", "features": []}

    def load(self, geojson_data):
        self.geojson_data = geojson_data

    def get_lines(self):
        return [
            feature for feature in self.geojson_data["features"]
            if feature["geometry"]["type"] == "LineString"
        ]

class TRACONDisplay(QMainWindow):
    def __init__(self, username, password):
        super().__init__()
        self.setWindowTitle("C90 TRACON Radar Display")
        self.setGeometry(100, 100, 800, 800)
        self.radar_center = QPointF(400, 400)
        self.aircraft_data = []
        self.scale_factor = 1.0
        self.offset = QPointF(0, 0)
        self.dragging = False
        self.last_pos = QPointF()

        self.geojson_loader = GeoJsonLoader()

        self.data_fetcher = DataFetcher(username, password)
        self.data_fetcher.data_fetched.connect(self.update_aircraft_data)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_fetching_data)
        self.timer.start(5000)

        # Set up the menu bar
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.live_atc_action = QAction("Play LiveATC.net (C90)", self)
        self.live_atc_action.triggered.connect(self.play_live_atc)
        self.file_menu.addAction(self.live_atc_action)

        self.load_geojson_action = QAction("Load GeoJSON", self)
        self.load_geojson_action.triggered.connect(self.load_geojson_file)
        self.file_menu.addAction(self.load_geojson_action)

        print("TRACONDisplay initialized.")

    def start_fetching_data(self):
        if not self.data_fetcher.isRunning():
            self.data_fetcher.start()

    def update_aircraft_data(self, data):
        self.aircraft_data = data
        self.update()

    def play_live_atc(self):
        """Play LiveATC.net stream for C90."""
        url = "https://www.liveatc.net/search/?icao=ORD"  # Adjust URL to match LiveATC.net C90 feed
        network_manager = QNetworkAccessManager(self)
        request = QNetworkRequest(url)
        reply = network_manager.get(request)
        player = QMediaPlayer(self)
        player.setMedia(QMediaContent(reply))
        player.play()
        print("Playing LiveATC.net feed.")

    def load_geojson_file(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(self, "Open GeoJSON File", "", "GeoJSON Files (*.geojson)")
        if file_path:
            try:
                with open(file_path, "r") as f:
                    geojson_data = json.load(f)
                    self.geojson_loader.load(geojson_data)
                    self.update()
            except Exception as e:
                print(f"Error loading GeoJSON file: {e}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))  # Black background
        self.draw_radar(painter)
        self.draw_aircraft(painter)
        self.draw_geojson_lines(painter)

    def draw_radar(self, painter):
        """Draw radar range rings."""
        pen = QPen(QColor(200, 200, 200))  # Grey-white rings
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(1, 10):
            painter.drawEllipse(self.radar_center + self.offset, i * 80 * self.scale_factor, i * 80 * self.scale_factor)

    def draw_aircraft(self, painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(31, 122, 255))  # Blue aircraft

        font = QFont("Roboto", 8)
        painter.setFont(font)

        # Radar center coordinates (O'Hare)
        center_lat, center_lon = 41.978611, -87.904724  

        for aircraft in self.aircraft_data:
            try:
                # Extract necessary data
                lat = aircraft[6]
                lon = aircraft[5]
                alt = aircraft[7]
                callsign = aircraft[1] if aircraft[1] else "N/A"
                speed = f"{int(aircraft[9])}" if aircraft[9] else "N/A"

                # Validate data
                if None in (lat, lon, alt) or not isinstance(alt, (int, float)):
                    continue

                # Filter by altitude
                alt = int(alt)
                if alt < 100:
                    continue

                # Calculate the distance from the radar center
                distance = self.haversine(center_lat, center_lon, lat, lon) / 1609.34  # Convert meters to miles
                if distance > 80:  # Skip aircraft beyond 150 miles
                    continue

                # Calculate altitude in hundreds of feet
                alt_in_hundreds = f"{alt // 100:03}"

                # Map coordinates to radar screen
                x, y = self.map_to_radar_coords(lat, lon)

                # Scale and translate to radar center
                x = self.radar_center.x() + (x * self.scale_factor) + self.offset.x()
                y = self.radar_center.y() - (y * self.scale_factor) + self.offset.y()

                # Draw aircraft dot (fixed size, independent of scale_factor)
                circle_radius = 5  # Fixed radius in pixels
                painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)

                # Assign sector
                sector = self.assign_sector(lat, lon, alt)

                # Calculate text size for proper centering
                text_rect = painter.boundingRect(QRectF(0, 0, 00, 00), Qt.AlignCenter, sector)
                text_width = text_rect.width()
                text_height = text_rect.height()

                # Center text in the middle of the blue circle
                painter.drawText(QPointF(x - text_width / 2, y + text_height / 4), sector)


                # Center text in the middle of the blue circle


                # Draw callsign above the aircraft dot
                painter.setPen(QColor(255, 255, 255))  # White text
                painter.drawText(QPointF(x + 10, y - 10), callsign)

                # Draw altitude, speed, and sector under the callsign
                painter.drawText(QPointF(x + 10, y + 5), f"{alt_in_hundreds}   {speed}")

            except (TypeError, ValueError) as e:
                print(f"Error processing aircraft data: {e}")
                continue




    def draw_geojson_lines(self, painter):
        lines = self.geojson_loader.get_lines()
        for line in lines:
            try:
                coordinates = line["geometry"]["coordinates"]
                color = line.get("properties", {}).get("color", "#FFFFFF")  # Default color: white
                thickness = line.get("properties", {}).get("thickness", 1)

                # Ensure thickness is an integer
                if not isinstance(thickness, int) or thickness is None:
                    thickness = 1

                pen = QPen(QColor(color))
                pen.setWidth(thickness)
                painter.setPen(pen)

                points = [
                    QPointF(
                        self.radar_center.x() + self.map_to_radar_coords(lat, lon)[0] * self.scale_factor + self.offset.x(),
                        self.radar_center.y() - self.map_to_radar_coords(lat, lon)[1] * self.scale_factor + self.offset.y()
                    )
                    for lon, lat in coordinates
                ]

                painter.drawPolyline(*points)
            except (KeyError, ValueError, TypeError) as e:
                print(f"Error drawing GeoJSON line: {e}")
                continue



    
    def map_to_radar_coords(self, lat, lon):
        center_lat, center_lon = 41.978611, -87.904724  # O'Hare coordinates
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

if __name__ == "__main__":
    username = "ethanm"
    password = "ethanMA1120"

    app = QApplication(sys.argv)
    radar = TRACONDisplay(username, password)
    radar.show()
    sys.exit(app.exec_())
