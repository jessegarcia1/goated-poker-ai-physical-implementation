from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
import uvicorn
from pokers import State
from typing import Optional

from scripts.playing_card_detection.detection_utils import detect_cards
from src.backend.agents import Agents

# how to run: python3 -m src.backend.endpoints
# to expose server to all computers on the network: below in code
app = FastAPI()

agents: Optional[Agents] = None

class CardImage(BaseModel):
    image_as_list: list
    count: int

class AgentsInfo(BaseModel):
    n_players: int
    n_agents: int

# Since State from pokers is a class built in another language pydantic cannot parse it and
# does not know how to build it. So I might have to pass in each param to a state and build
# it here.
class GameState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    agent_pos: int
    game_state: State

@app.get("/is-backend-up", status_code=200)
def is_backend_up():
    return {"status": "Up and running!"}

@app.post("/load-models", status_code=200)
def load_models(data: AgentsInfo):
    n_players = data.n_players
    n_agents = data.n_agents
    
    agents = Agents(n_players, n_agents)
    status = agents.load_agents()
    
    return {"status": status, "num_agents": n_agents}
    
@app.post("/card-detection", status_code=200)
def card_detection(data: CardImage):
    if agents is None:
        raise HTTPException(status_code=400, detail="Models not loaded yet. Call /load-models first.")
    
    image = data.image_as_list
    count = data.count
    
    card_list = detect_cards(image, count)
    print(card_list)
    
    status = "ok"    
    if card_list == None:
        status == "failed"
        
    return {"status": status, "card_list": card_list}

@app.post("/choose-action", status_code=200)
def choose_action(data: GameState):
    global agents 
    
    if agents is None:
        raise HTTPException(status_code=400, detail="Models not loaded yet. Call /load-models first.")

    agent_pos = data.agent_pos
    game_state = data.game_state
    
    agent = agents.agent_list[agent_pos]
    action = agent.choose_action(game_state)
    
    return {"action": action.action, "amount": action.amount}
    

# used to expose backend to other local guys
if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=8000)