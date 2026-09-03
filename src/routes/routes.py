from dotenv import load_dotenv
import os

load_dotenv()

local_ip = os.getenv("LOCAL_IP")
mac_tailscale_ip = os.getenv("MAC_TAILSCALE_IP")

urls = {
  "local-ip": "http://" + local_ip + ":8000",
  "mac-tailscale-ip": "http://" + mac_tailscale_ip + ":8000"
}

routes = {
  "card-detection": "/card-detection",
  "is-backend-up": "/is-backend-up",
  "choose-action": "/choose-action",
  "load-models": "/load-models",
  "play-text-to-speech": "/play-text-to-speech"
}