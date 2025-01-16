import os
import shutil
import json

def search_and_copy_geojson_files(source_folder, destination_folder, keyword):
    # Check if source and destination folders exist
    if not os.path.exists(source_folder):
        print(f"Source folder '{source_folder}' does not exist.")
        return
    if not os.path.exists(destination_folder):
        print(f"Destination folder '{destination_folder}' does not exist.")
        return
    
    # Search for geojson files and check the content for the keyword
    for filename in os.listdir(source_folder):
        if filename.endswith(".geojson"):
            source_file = os.path.join(source_folder, filename)
            
            try:
                # Open and read the GeoJSON file
                with open(source_file, 'r', encoding='utf-8') as file:
                    geojson_data = json.load(file)
                    
                    # Check if the keyword exists in the content
                    # This checks all properties, not just specific keys
                    def search_recursive(data):
                        if isinstance(data, dict):
                            for key, value in data.items():
                                if isinstance(value, (dict, list)):
                                    if search_recursive(value):
                                        return True
                                elif isinstance(value, str) and keyword.lower() in value.lower():
                                    return True
                        elif isinstance(data, list):
                            for item in data:
                                if search_recursive(item):
                                    return True
                        return False
                    
                    # If keyword found in any part of the file, copy it
                    if search_recursive(geojson_data):
                        destination_file = os.path.join(destination_folder, filename)
                        shutil.copy(source_file, destination_file)
                        print(f"Copied '{filename}' to '{destination_folder}'")
            
            except Exception as e:
                print(f"Error processing {filename}: {e}")

# Example usage
source_folder = r"C:\Users\abbym\Documents\CRC\VideoMaps\ZSE"  # Replace with the path to the source folder
destination_folder = r"C:\Users\abbym\Documents\RadarView\Resources\tracons"  # Replace with the path to the destination folder
keyword = input("Enter the keyword to search for in the file content: ")  # You can enter 'pdx' or any other keyword

search_and_copy_geojson_files(source_folder, destination_folder, keyword)
