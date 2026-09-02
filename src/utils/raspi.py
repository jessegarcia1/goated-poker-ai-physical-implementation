#raspi.py
import cv2
from pokers import State, Card
import numpy as np
import serial
import time

from dataclasses import dataclass

"""
    How to run: run with sudo
"""
def capture_photo(camera_num: int, file_name: str=None):
    """
    Captures an image with the camera of the chosen number. 
    Writes the image to a file if name is specified. Remember the file extension (.jpg)
    
    Args:
        camera_num: Number of the camera to take the photo, 0 indexing
        file_name: Name of the image file to save
    Returns:
        Image of photo in python list (so it can be sent via json)
    """
    cap = cv2.VideoCapture(camera_num)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera {camera_num}")

    # Some cameras need a few frames "flushed" before the image is stable
    for _ in range(5):
        ret, frame = cap.read()

    ret, frame = cap.read()

    if file_name != None:
        cv2.imwrite(filename=file_name, img=frame)

    cap.release()
    
    return np.array(frame).tolist()

@dataclass
class PhysicalGameState:
    num_players: int
    num_agents: int
    initial_stake: float
    button_pos: int
    small_blind: float
    big_blind: float

def get_serial_gamestate_info(port='/dev/ttyACM0', baudrate=9600, skip=False):
    if skip:
        return PhysicalGameState(
            num_players=4,
            num_agents=2,
            initial_stake=10.00,
            button_pos=1,
            small_blind=.25,
            big_blind=.50,
        )
    else:
        ser = serial.Serial(port, baudrate, timeout=None)

        num_players = int(ser.readline().decode().strip())
        num_agents = int(ser.readline().decode().strip())
        initial_stake = float(ser.readline().decode().strip())
        button_pos = int(ser.readline().decode().strip())
        small_blind = float(ser.readline().decode().strip())
        big_blind = float(ser.readline().decode().strip())

        ser.close()

        return PhysicalGameState(
            num_players=num_players,
            num_agents=num_agents,
            initial_stake=initial_stake,
            button_pos=button_pos,
            small_blind=small_blind,
            big_blind=big_blind,
        )

def get_serial_pot_amount(port='/dev/ttyACM0', baudrate=9600, tare=False, verbose=True):
    """
    Communicates with the Arduino over serial to tare the scale
    and retrieve the average pot weight. 
    It then divides it by the weight of a chip to get the amount of chips in the pot

    Returns:
        float: The value of the current pot. This value gets zero'd after it is read.

    Raises:
        RuntimeError: If the tare or weight reading times out.
    """
    if verbose: 
        print("Waiting for scale to get five weights..." )
    if not tare:
        for i in range(5):
            print(i + 1)
            time.sleep(1)
   
    TIMEOUT = 20 # in seconds

    ser = serial.Serial(port, baudrate, timeout=1)
    
    # Clear any startup messages already waiting in the serial buffer
    ser.reset_input_buffer()

    if verbose:
        print("Sending GET_WEIGHT command...")
    
    ser.write(b"GET_WEIGHT\n")
    ser.flush()

    start_time = time.time()

    while time.time() - start_time < TIMEOUT:

        line = ser.readline().decode().strip()
        if not line:
            continue

        if line.startswith("AVERAGE_WEIGHT:"):
            try:
                weight_string = line.split(":", 1)[1].strip()
                weight = float(weight_string)

                if verbose:
                    print(f"Average pot weight: {weight:.2f} g")
                rounded_num_chips = round(weight / 10.5) # 10.5 is the weight of 1 chip
                pot_value = rounded_num_chips * .25
                if verbose:
                    print(f"Current pot value: ${pot_value}")
                return pot_value

            except (IndexError, ValueError) as error:
                raise RuntimeError(
                    f"Could not parse weight from: {line}"
                ) from error

    # Timeout occurred
    raise RuntimeError(
        "Timed out waiting for the Arduino to return the weight."
    )
        
def card_to_string(card: Card) -> str:
    """Convert a poker card to a json parsable string."""
    suits = {0: "C", 1: "D", 2: "H", 3: "S"}
    ranks = {0: "2", 1: "3", 2: "4", 3: "5", 4: "6", 5: "7", 6: "8", 
             7: "9", 8: "T", 9: "J", 10: "Q", 11: "K", 12: "A"}
    
    return f"{suits[int(card.suit)]}{ranks[int(card.rank)]}"

def create_state_json_payload(state: State, n_players: int, seed: int) -> dict:
    """
        Create a json parsable payload of a State that can be sent via FastAPI.
        
        Args:
            state: The current State of the poker game to send
            n_players: Number of players in the game
            seed: The random seed the State was created with
        Returns: 
            json parsable dict.
    """
    # Primitive
    button = state.button
    current_player = state.current_player
    pot = state.pot
    min_bet = state.min_bet
    final_state = state.final_state

    # list[str]
    public_cards_strings = [card_to_string(card) for card in state.public_cards]
    deck_strings = [card_to_string(card) for card in state.deck]

    # list[str] (stringified enums)
    legal_actions = [int(action) for action in state.legal_actions]

    # Build a payload entry for every player instead of just players_state[0]
    players_state_payload = []
    for player_state in state.players_state:
        players_state_payload.append({
            "active": player_state.active,
            "bet_chips": player_state.bet_chips,
            "hand": [card_to_string(card) for card in player_state.hand],  # should be rebuilt as tuple[Card, Card]
            "player": player_state.player,
            "pot_chips": player_state.pot_chips,
            "reward": player_state.reward,
            "stake": player_state.stake,
        })

    stage = int(state.stage)

    payload = {
        "n_players": n_players,
        "button": button,
        "current_player": current_player,
        "pot": pot,
        "min_bet": min_bet,
        "final_state": final_state,
        "public_cards": public_cards_strings,
        "deck": deck_strings,
        "legal_actions": legal_actions,
        "players_state": players_state_payload,
        "stage": stage,
        "seed": seed
    }
    
    print(payload)
    
    return payload

if __name__ == '__main__':
    get_serial_pot_amount()
