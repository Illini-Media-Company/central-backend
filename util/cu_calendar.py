import os
import googlemaps
from db.cu_calender import add_event

def geocode_address(address):
    api_key = os.getenv('FLASK_GEOCODING_API_KEY')

    if not api_key:
        print("Error: Google API key not found.")
        return None
    
    gmaps = googlemaps.Client(key=api_key)

    try:
        geocode_result = gmaps.geocode(address)

        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            return location['lat'], location['lng']
        else:
            return None
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return None
    

def gcal_to_events(gcal_url):
    #todo
    
    return []
    
