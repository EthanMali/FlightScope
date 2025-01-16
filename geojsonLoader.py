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