from pokers import Card, State, Stage, ActionEnum
from pydantic import BaseModel

"""
    python -m src.backend.backend_utils
"""

class PlayerStatePayload(BaseModel):
    active: bool
    bet_chips: float
    hand: list[str]          # ["As", "Kd"]
    player: int
    pot_chips: float
    reward: float
    stake: float

class GameStatePayload(BaseModel):
    n_players: int
    button: int
    current_player: int
    pot: float
    min_bet: float
    final_state: bool
    public_cards: list[str]
    deck: list[str]
    legal_actions: list[int]   
    players_state: list[PlayerStatePayload]
    stage: int
    seed: int
    
def create_state_from_json(payload: GameStatePayload) -> State:
    """
    Reconstruct a State object from a payload produced by create_state_json_payload.

    Args:
        payload: dict created by create_state_json_payload
    Returns:
        Reconstructed State
    """
    print(payload)
    state = State.from_seed(
        n_players=payload.n_players,
        button=payload.button,
        sb=0,
        bb=0,
        stake=0,
        seed=payload.seed,
    )

    state.current_player = payload.current_player
    state.pot = payload.pot
    state.min_bet = payload.min_bet
    state.final_state = payload.final_state

    stages = {0: Stage.Preflop, 1: Stage.Flop, 2: Stage.Turn, 3: Stage.River, 4: Stage.Showdown}
    state.stage = stages[payload.stage]

    state.public_cards = [Card.from_string(card) for card in payload.public_cards]
    state.deck = [Card.from_string(card) for card in payload.deck]

    # get the copy, mutate, then reassign back to state 
    players_copy = state.players_state
    for player_id, player_payload in enumerate(payload.players_state):
        player_state = players_copy[player_id]
        player_state.active = player_payload.active
        player_state.bet_chips = player_payload.bet_chips
        player_state.hand = tuple(Card.from_string(card) for card in player_payload.hand)
        player_state.player = player_payload.player
        player_state.pot_chips = player_payload.pot_chips
        player_state.reward = player_payload.reward
        player_state.stake = player_payload.stake
        players_copy[player_id] = player_state
    state.players_state = players_copy
    
    actions = {0: ActionEnum.Fold, 1: ActionEnum.Check, 2: ActionEnum.Call, 3: ActionEnum.Raise}
    state.legal_actions = [actions[a] for a in payload.legal_actions]
    
    return state

# payload = {'n_players': 6, 'button': 1, 'current_player': 4, 'pot': 0.75, 'min_bet': 0.5, 'final_state': False, 'public_cards': [], 'deck': ['D9', 'C7', 'SQ', 'S2', 'HA', 'CK', 'CJ', 'HQ', 'D5', 'HJ', 'ST', 'C8', 'D2', 'S4', 'DT', 'S7', 'C5', 'D8', 'H2', 'HT', 'H5', 'SK', 'D4', 'S6', 'DQ', 'DA', 'H8', 'SJ', 'S8', 'S5', 'D6', 'CA', 'H4', 'S3', 'D3', 'HK', 'C9', 'C3', 'H3', 'D7'], 'legal_actions': [0, 2, 3], 'players_state': [{'active': True, 'bet_chips': 0.0, 'hand': ['CQ', 'H9'], 'player': 0, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 10.0}, {'active': True, 'bet_chips': 0.0, 'hand': ['DK', 'CT'], 'player': 1, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 10.0}, {'active': True, 'bet_chips': 0.25, 'hand': ['C4', 'S9'], 'player': 2, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 9.75}, {'active': True, 'bet_chips': 0.5, 'hand': ['SA', 'DJ'], 'player': 3, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 9.5}, {'active': True, 'bet_chips': 0.0, 'hand': ['C4', 'DA'], 'player': 4, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 10.0}, {'active': True, 'bet_chips': 0.0, 'hand': ['C4', 'DA'], 'player': 5, 'pot_chips': 0.0, 'reward': 0.0, 'stake': 10.0}], 'stage': 0, 'seed': 2112}
# if __name__ == '__main__':
#     state = create_state_from_json(payload)
#     print(state)
    