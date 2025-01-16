
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