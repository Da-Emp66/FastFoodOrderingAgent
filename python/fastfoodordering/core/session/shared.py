from pathlib import Path
from typing import Dict
import docker
from docker.models.containers import Container
from core.session.session import SessionManager

docker_client = docker.from_env()
session_manager = SessionManager(Path(__file__).parent.parent.parent / "configuration" / "session_manager.yaml")
session_ids_to_containers: Dict[str, Container] = {}
