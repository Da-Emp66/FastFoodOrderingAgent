import json
import os
from uuid import uuid4

import yaml
from core.session.serve import docker_client, session_manager
from core.session.session import BrowserGeoLocation
from core.utils import populate_environment_specifications

WEB_AGENT_IMAGE = os.getenv("WEB_AGENT_IMAGE", "web-agent")
WEB_AGENT_TAG = os.getenv("WEB_AGENT_TAG", "latest")

async def start_session(
    order: str,
    user: str,
    current_geolocation: BrowserGeoLocation,
):
    user = user.replace("{", "").replace("}", "") # STRONG TODO: LLM should not generate user, current_geolocation
    session_id = str(uuid4())
    container_environment_vars = os.environ.copy()
    container_environment_vars.update({
        "_DYN_WEB_AGENT_USER": user,
        "_DYN_WEB_AGENT_SESSION_ID": session_id,
        "SESSION_USER": user,
        "SESSION_ID": session_id,
        "SESSION_OBJECTIVE": order,
        "BROWSER_GEOLOCATION": json.dumps(current_geolocation),
    })
    web_agent_environment_spec = populate_environment_specifications(
        session_manager.configuration.web_agent_spec,
        _DYN_WEB_AGENT_USER=user,
        _DYN_WEB_AGENT_SESSION_ID=session_id,
    )
    print(f"Starting user `{user}`'s session `{session_id}` with the following spec:")
    print(yaml.safe_dump(web_agent_environment_spec))
    if "volumes" in web_agent_environment_spec:
        volumes = web_agent_environment_spec["volumes"]
        absolute_path_volumes = []
        for volume_mount_spec in volumes:
            host_path, path_inside_container = tuple(volume_mount_spec.split(':'))
            absolute_path_volumes.append(f"{os.path.abspath(host_path)}:{path_inside_container}")
        web_agent_environment_spec.update({ "volumes": absolute_path_volumes })
    container = docker_client.containers.run(
        **web_agent_environment_spec,
        restart_policy={"Name": "always"},
        environment=container_environment_vars,
        detach=True,
    )
    return f"Session started as container ${container}. The session ID is {session_id}."

async def update_session(
    user: str,
    session_id: str,
):
    return f"Session with ID {session_id} for user {user} updated."

async def cancel_session(
    user: str,
    session_id: str,
):
    container_name = populate_environment_specifications(session_manager.configuration.web_agent_spec["name"])
    container = docker_client.containers.get(container_name)
    container.stop()
    container.remove()
    return f"Session with ID {session_id} for user {user} canceled."
