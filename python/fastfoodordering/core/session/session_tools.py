import json
import os
from typing import Union
from uuid import uuid4

import requests
import yaml
import shared
from core.session.session import BrowserGeoLocation, ObjectiveSpecification, Session, SessionManagerToolCallResult
from core.utils import populate_environment_specifications, remove_special_characters

WEB_AGENT_IMAGE = os.getenv("WEB_AGENT_IMAGE", "web-agent")
WEB_AGENT_TAG = os.getenv("WEB_AGENT_TAG", "latest")

async def start_session(
    exact_user_query: str,
    user: str,
    current_geolocation: BrowserGeoLocation,
) -> Union[str, "SessionManagerToolCallResult"]:
    # user = user.replace("{", "").replace("}", "")
    user_without_special_characters = remove_special_characters(user)
    session_id = str(uuid4())
    container_environment_vars = os.environ.copy()
    
    replacements = {}
    for key, val in container_environment_vars.items():
        val = val.replace("localhost", "host.docker.internal")
        replacements[key] = val
    container_environment_vars.update(replacements)
    
    container_environment_vars.update({
        "_DYN_WEB_AGENT_USER": user_without_special_characters,
        "_DYN_WEB_AGENT_SESSION_ID": session_id,
        "SESSION_USER": user,
        "SESSION_ID": session_id,
        "SESSION_OBJECTIVE": exact_user_query,
        "BROWSER_GEOLOCATION": current_geolocation.model_dump_json(),
        # "BROWSER_AGENT_TYPE": ,
        # "PLAYWRIGHT_BROWSERS_PATH": "/root/.cache/ms-playwright",
    })
    web_agent_environment_spec = populate_environment_specifications(
        shared.session_manager.configuration.web_agent_spec,
        _DYN_WEB_AGENT_USER=user_without_special_characters,
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
    print(shared.docker_client.networks.list())
    network = shared.docker_client.networks.get(os.getenv("DOCKER_NETWORK_NAME", "fast-food"))
    print(network)
    container = shared.docker_client.containers.run(
        **web_agent_environment_spec,
        network=network.name,
        extra_hosts={"host.docker.internal": "host-gateway"},
        restart_policy={"Name": "always"},
        environment=container_environment_vars,
        detach=True,
    )
    shared.session_ids_to_containers[session_id] = container
    print(shared.session_ids_to_containers)
    return SessionManagerToolCallResult(
        result=f"Session started as container ${container}. The session ID is {session_id}.",
        session_id=session_id,
    ).model_dump_json()

async def update_session(
    user: str,
    session_id: str,
    updated_objective_spec: ObjectiveSpecification,
) -> Union[str, "SessionManagerToolCallResult"]:
    user_without_special_characters = remove_special_characters(user)
    response = requests.put(f"http://{user_without_special_characters}-session-{session_id}:9000/active-session", data=Session(
        user=user,
        session_id=session_id,
        objective_spec=updated_objective_spec,
    ))

    if response.status_code != 200:
        return f"Failed to update session with ID {session_id} for user {user}: {response.text}"

    return SessionManagerToolCallResult(result=f"Session with ID {session_id} for user {user} updated.").model_dump_json()

async def cancel_session(
    user: str,
    session_id: str,
) -> Union[str, "SessionManagerToolCallResult"]:
    # container_name = populate_environment_specifications(shared.session_manager.configuration.web_agent_spec["name"])
    # container = shared.docker_client.containers.get(container_name)
    # OR
    container = shared.session_ids_to_containers.get(session_id)
    if container is None:
        return SessionManagerToolCallResult(result=f"Failed to cancel session!!! Session with ID {session_id} for user {user} does not exist.").model_dump_json()
    container_id = container.id
    container = shared.docker_client.containers.get(container_id)
    container.stop()
    container.remove()
    shared.session_ids_to_containers.pop(session_id)
    return SessionManagerToolCallResult(result=f"Session with ID {session_id} for user {user} canceled successfully.").model_dump_json()
