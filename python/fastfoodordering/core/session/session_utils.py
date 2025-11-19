import math
import traceback
from typing import List, Union

from pydantic import BaseModel

class LatitudeLongitudeCoordinate(BaseModel):
    latitude: float
    longitude: float

class RetrievedLocation(BaseModel):
    name: str
    address: str
    distance: float
    location: LatitudeLongitudeCoordinate

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    """
    R = 6371  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_restaurant_locations_nearby(
    latitude: float,
    longitude: float,
    restaurant_name_or_food_chain: str,
) -> Union[str, List[RetrievedLocation]]:
    """Example kwargs:
    latitude = 40.748817
    longitude = -73.985428
    restaurant_name_or_food_chain = "McDonald's"
    """
    import shared
    if shared.gmaps is None:
        return "Restaurant finding with Google Maps is not enabled for your account. Unable to get restaurants nearby."

    try:
        results = shared.gmaps.places_nearby(
            location=(latitude, longitude),
            keyword=restaurant_name_or_food_chain,
            type="restaurant",
            rank_by="distance",
            # radius=50000, # 50km
        )

        if results.get("results", None) is not None:
            locations = []
            for result in results["results"]:
                locations.append(
                    RetrievedLocation(
                        name=result["name"],
                        address=result["vicinity"],
                        distance=haversine_distance(
                            latitude,
                            longitude,
                            result["geometry"]["location"]["lat"],
                            result["geometry"]["location"]["lng"],
                        ),
                        location=LatitudeLongitudeCoordinate(
                            latitude=result["geometry"]["location"]["lat"],
                            longitude=result["geometry"]["location"]["lng"],
                        ),
                    )
                )
            locations = sorted(locations, key=lambda x: x.distance)
            return locations
        else:
            return f"No locations similar to the name {restaurant_name_or_food_chain} found nearby."
    except Exception as e:
        traceback.format_exc()
        return str(e)

if __name__ == "__main__":
    print(get_restaurant_locations_nearby(40.748817, -73.985428, "McDonald's"))
