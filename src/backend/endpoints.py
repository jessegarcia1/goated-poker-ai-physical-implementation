from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from pokers import State

from scripts.playing_card_detection.detection_utils import detect_cards
from src.core.deep_cfr import DeepCFRAgent


# how to run: run file
# to expose server to all computers on the network: below in code

# how to set interpreter: run 'source ./.venv/bin/activate' in command line. 
# this makes sure packages get installed into this venv (and not another or global) by changing the path variables
# then select interpreter in vscode: ./venv/bin/python3

app = FastAPI()


class CardImage(BaseModel):
  image_as_list: list

class GameState(BaseModel):
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
  uvicorn.run("endpoints:app", host="0.0.0.0", port=8000)