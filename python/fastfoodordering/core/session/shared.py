from distutils.util import strtobool
import os
from pathlib import Path
from typing import Dict
import docker
from docker.models.containers import Container
from core.session.session import SessionManager

docker_client = docker.from_env()
session_manager = SessionManager(Path(__file__).parent.parent.parent / "configuration" / "session_manager.yaml")
session_ids_to_containers: Dict[str, Container] = {}

gmaps = None
if strtobool(os.getenv("ENABLE_PAYMENTS", "false")) is not None:
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", None)
    if GOOGLE_MAPS_API_KEY is not None:
        import googlemaps
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
