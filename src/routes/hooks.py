from src.routes.routes import routes, urls
import requests
import time

def handle_post_request(payload: dict, route_key: str, timeout: float=10.0):
    """
        Handles sending out a post request.
        
        Args:
            payload: Payload to send in the post requests
            route_key: The route to hit in the backend
            timeout: Timeout in seconds
        Returns:
            The parsed JSON response body.
    """
    headers = {"content-type": "application/json"}
    url = urls["mac-tailscale-ip"] + routes[route_key]

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as err:
        print(f"Request to {url} failed: {err}")
        raise

    if response.status_code == 204:
        raise Exception("POST request receives status of 204, response = { }")

    try:
        return response.json()
    except ValueError as err:
        print(f"Failed to parse JSON response from {url}: {err}")
        raise

def handle_get_request(payload: dict, route_key: str, timeout: float=10.0):
    """
        Handles sending out a get request.
        
        Args:
            payload: Payload to send in the post requests
            route_key: The route to hit in the backend
            timeout: Timeout in seconds
        Returns:
            The parsed returned response.
    """
    headers = {"content-type": "application/json"}
    url = urls["mac-tailscale-ip"] + routes[route_key]

    try:
        response = requests.get(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as err:
        print(f"Request to {url} failed: {err}")
        raise

    if response.status_code == 204:
        raise Exception("GET request receives status of 204, response = { }")

    try:
        return response
    except ValueError as err:
        print(f"Failed to parse JSON response from {url}: {err}")
        raise

def is_backend_up_hook():
    payload={}
    response = handle_get_request(payload=payload, route_key="is-backend-up")

    if (response.status_code != 200):
        raise Exception("Backend is not up!")
    
    return "ok"
    
def text_to_speech_hook(text:str, skip=False, sleep=4):
    """
        Handles text to speech. 
        Sleeps for 4 seconds so players can hear text. 
        If skip=True the function will not sleep.
    """
    # sometimes audio clips a little at start
    text = "  " + text
    payload = {"text": text}
    response = handle_get_request(payload=payload, route_key="play-text-to-speech")
    if not skip:
        time.sleep(sleep)
        
    return "ok"

def card_detection_hook(image_as_list, count: int, timeout: float = 20.0):
    payload = {"image_as_list": image_as_list, "count": count}
    
    return handle_post_request(payload=payload, route_key="card-detection", timeout=timeout)

def load_models_hook(n_players: int, n_agents: int):
    payload = {"n_players": n_players, "n_agents": n_agents}
    
    return handle_post_request(payload=payload, route_key="load-models")

def choose_action_hook(game_state, agent_pos: int):
    payload = {"game_state": game_state, "agent_pos": agent_pos}
    
    return handle_post_request(payload=payload, route_key="choose-action")