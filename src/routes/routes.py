from dotenv import load_dotenv
import os

load_dotenv()

local_ip = os.getenv("LOCAL_IP")
tailscale_ip = os.getenv("TAILSCALE_IP")

urls = {
  "local-ip-8000": "http://" + local_ip,
  "mac-tailscale": "http://" + tailscale_ip
}

routes = {
  "card-detection": "/card-detection",
  "is-backend-up": "/is-backend-up",
  "choose-action": "/choose-action",
  "load-models": "/load-models"
}