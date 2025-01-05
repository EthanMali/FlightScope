import sys
import requests
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtCore import Qt, QPointF, QTimer, QThread, pyqtSignal


class DataFetcher(QThread):
    data_fetched = pyqtSignal(list)

    def run(self):
        """Fetch aircraft data in a separate thread."""
        url = "https://opensky-network.org/api/states/all"
        params = {"lamin": 41.5, "lomin": -88, "lamax": 42.5, "lomax": -87}  # C90 TRACON area
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            aircraft_data = [
                self.enrich_aircraft_data(state)
                for state in data.get("states", [])
                if state[7] and state[7] > 500  # Exclude ground
            ]
            self.data_fetched.emit(aircraft_data)
        except requests.RequestException as e:
            print(f"Error fetching aircraft data: {e}")
            self.data_fetched.emit([])

    def enrich_aircraft_data(self, state):
        """Enrich data without aircraft type and destination."""
        state.append("Unknown")  # Placeholder for destination
        state.append("Unknown")  # Placeholder for aircraft type
        return state


class TRACONDisplay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("C90 TRACON Radar Display")
        self.setGeometry(100, 100, 800, 800)
        self.radar_center = QPointF(400, 400)
        self.aircraft_data = []

        # Initialize the data fetcher thread
        self.data_fetcher = DataFetcher()
        self.data_fetcher.data_fetched.connect(self.update_aircraft_data)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_fetching_data)
        self.timer.start(5000)  # Fetch every 5 seconds

        self.start_fetching_data()

    def start_fetching_data(self):
        """Start fetching data using the background thread."""
        if not self.data_fetcher.isRunning():
            self.data_fetcher.start()

    def update_aircraft_data(self, data):
        """Update the aircraft data."""
        self.aircraft_data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0))  # Black background
        self.draw_radar(painter)
        self.draw_aircraft(painter)

    def draw_radar(self, painter):
        """Draw radar range rings."""
        pen = QPen(QColor(200, 200, 200))  # Grey-white rings
        pen.setWidth(2)
        painter.setPen(pen)

        # Draw concentric range rings
        for i in range(1, 6):
            painter.drawEllipse(self.radar_center, i * 80, i * 80)

    def draw_aircraft(self, painter):
        """Draw aircraft icons and data."""
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(31, 122, 255, 255))  # White dots

        font = QFont("Roboto", 8)
        painter.setFont(font)

        for aircraft in self.aircraft_data:
            try:
                lat, lon, alt = aircraft[6], aircraft[5], aircraft[7]
                alt = int(alt) if alt else 0
                alt_in_hundreds = f"{alt // 100:03}"  # Format altitude in hundreds of feet
                if alt < 500:  # Exclude low altitudes
                    continue

                speed = f"{int(aircraft[9]) if aircraft[9] else 'N/A'}"  # Get speed or 'N/A'

                x, y = self.map_to_radar_coords(lat, lon)
                sector = self.assign_sector(lat, lon, alt)

                # Draw aircraft dot
                painter.drawEllipse(QPointF(x, y), 8, 8)
                painter.setPen(QColor(0, 0, 0))  # Black for sector text
                painter.drawText(QPointF(x - 4, y + 4), sector)  # Draw sector inside dot

                # Draw callsign and data tag
                callsign = aircraft[1]
                painter.setPen(QColor(255, 255, 255))  # White text
                painter.drawText(QPointF(x + 10, y - 10), callsign)  # Callsign above dot

                # Draw altitude and speed below dot
                painter.drawText(QPointF(x + 10, y + 10), f"{alt_in_hundreds} | {speed}")
            except (TypeError, ValueError):
                continue

    def map_to_radar_coords(self, lat, lon):
        """Convert lat/lon to radar screen coordinates."""
        # C90 TRACON centered around O'Hare (41.978611, -87.904724)
        center_lat, center_lon = 41.978611, -87.904724
        scale = 800  # Scaling factor for visual representation
        x = self.radar_center.x() + (lon - center_lon) * scale
        y = self.radar_center.y() - (lat - center_lat) * scale
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    radar = TRACONDisplay()
    radar.show()
    sys.exit(app.exec_())
