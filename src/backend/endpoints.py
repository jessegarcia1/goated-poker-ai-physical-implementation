from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
import uvicorn
from pokers import State

from scripts.playing_card_detection.detection_utils import detect_cards
from src.core.deep_cfr import DeepCFRAgent


# how to run: python3 -m src.backend.endpoints
# to expose server to all computers on the network: below in code
app = FastAPI()

class CardImage(BaseModel):
  image_as_list: list

# Since State from pokers is a class built in another language pydantic cannot parse it and
# does not know how to build it. So I might have to pass in each param to a state and build
# it here.
class GameState(BaseModel):
  model_config = ConfigDict(arbitrary_types_allowed=True)
  game_state: State

@app.get("/is-backend-up", status_code=200)
def is_backend_up():
  return "Up and running!"

@app.post("/card-recognition", status_code=200)
def card_recognition(data: CardImage): # these functions DO take in any params and it will be in the 'image'
  image = data.image_as_list

  card_list = detect_cards(image)
  print("Recognized cards", card_list)

  json_response = {
    'card_list': card_list
    }
  
  return json_response

@app.post("/choose-action", status_code=200)
def choose_action(data: GameState):
  state = data.game_state
  
  agent = DeepCFRAgent()


# used to expose backend to other local guys
if __name__ == "__main__":
  uvicorn.run(app=app, host="0.0.0.0", port=8000)