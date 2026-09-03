import pokers as pkrs
import random
import requests
import cv2
import numpy as np
import time

from pokers import Card, Action, State, ActionEnum
from scripts.play_helpers import card_to_string, get_action_description, display_game_state, get_human_action_physical_game
from scripts.raspi_gpio_scripts.get_player_action import wait_for_player_action
from scripts.raspi_gpio_scripts.dispense_chips import dispense, homing_sequence, move_pot
from src.utils import apply_action_with_logging
from src.utils.raspi import capture_photo, get_serial_gamestate_info, create_state_json_payload, get_serial_pot_amount
from src.routes.routes import urls, routes
from src.utils.actions import raise_bounds
from src.routes.hooks import card_detection_hook, load_models_hook, choose_action_hook, text_to_speech_hook, is_backend_up_hook

"""
    To run: python3 -m scripts.play_physical 
"""
class PhysicalGame:
    """
    Manages a persistent physical poker game session.
    """

    def __init__(
        self,
        n_players: int,
        button_pos: int,
        initial_stake: float,
        num_agents: int,
        small_blind: float = 1.0,
        big_blind: float = 2.0,
    ):
        if n_players <= 1:
            raise ValueError("Need at least 2 players")
        
        self.n_players = n_players
        self.button_pos = button_pos
        self.initial_stake = initial_stake
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.num_human_players = n_players - num_agents
        self.num_agents = num_agents
        self.seed = None
        self.AGENT_HANDS_CAMERA_NUM = 0
        self.COMMUNITY_CARDS_CAMERA_NUM = 2

        # Humans occupy first N seats by default
        self.human_positions = list(range(self.num_human_players))
        # Agents occupy remaining seats
        self.agent_positions = list(
            range(self.num_human_players, n_players)
        )

        # Bankroll tracking
        self.player_stakes = {
            player_id: initial_stake
            for player_id in range(n_players)
        }
        
        self.state = None
        self.agents = [None] * n_players
        
    def action_enum_from_int(self, action_int: int) -> ActionEnum:
        """
            Returns an ActionEnum from an int(Action).
        """
        actions = {0: ActionEnum.Fold, 1: ActionEnum.Check, 2: ActionEnum.Call, 3: ActionEnum.Raise}
        action = actions[action_int]
        return action

    def create_state(self):
        """
            Create a new poker state using current bankrolls.
        """        
        self.seed = random.randint(0, 10000)
        
        self.state = State.from_seed(
            n_players=self.n_players,
            button=self.button_pos,
            sb=self.small_blind,
            bb=self.big_blind,
            stake=self.initial_stake,
            seed=self.seed
        )

        # Manually overwrite player stakes. 
        # Agent stakes will be tracked and updated.
        # Human stakes will always be the initial_stake becausee these cannot be tracked.
        # TODO: Make it so humans can bet over inital_stake. 
        players = self.state.players_state # players is a copy of players_state
        for player_id, player_state in enumerate(players):
            if player_id in self.agent_positions:
                player_state.stake = self.player_stakes[player_id]
                players[player_id] = player_state
            else:
                print(f"Skipped overwriting stake for player number {player_id}")

        self.state.players_state = players

        return self.state

    def set_cards(self, count: int, camera_num: int, prompt: str=None, detect=False)-> list[Card] | None:
        """
        Detect cards from an image or if prompt != None,
        prompt the user to enter cards from the physical table.
        
        Args:
            count: How many cards to capture
            prompt: Description of which cards to enter
        """
        # If there is a prompt collect card data manually, otherwise collect via camera.
        if not detect:
            print(f"\n{prompt}")
            print(f"Enter {count} card(s) using format: suit+rank (e.g. SA=Ace of Spades, HK=King of Hearts, C2=2 of Clubs, DT=10 of Diamonds)")
            
            while True:
                raw_cards = input(f"Cards (space-separated): ").upper().strip().split()
 
                if len(raw_cards) != count:
                    print(f"Please enter exactly {count} card(s).")
                    continue
                
                if any(c is None or len(c) > 2 for c in raw_cards):
                    print("One or more cards were invalid. Try again.")
                    continue
                
                card_objects = [Card.from_string(c) for c in raw_cards]
                
                # Show what was parsed for confirmation
                readable = [f"{card_to_string(o)}" for o in card_objects]
                confirm = input(f"Confirm: {' '.join(readable)}? (y/n): ").strip().lower()
                if confirm == "y":
                    print("\n")
                    return card_objects
        else:
            print(f"\n{prompt}")
            status = "failed"
            max_tries = 3 # This will capture 3 photos at max
            
            for attempt in range(max_tries):
                try:
                    image = capture_photo(camera_num, "test123.jpg")

                    print('Sending photo...\n')
                    data = card_detection_hook(image, count)

                    status = data["status"]
                    print("detection status: ", status)
                    
                    if status == "ok":
                        card_list = [Card.from_string(card) for card in data["card_list"]]
                        return card_list
                    
                except requests.exceptions.RequestException as e:
                    print(e)
                    pass
                
            raise Exception(f"ERROR: {count} Cards failed to be set.")

    def get_nearest_quarter_amount(self, action: Action):
        """
        Rounds the amount of the action to the nearest .25 cents. Always rounds down.
        If Call action:
            Sets Call action to have its value be the min_raise amount (prev action amount).
        """
        if action.action == pkrs.ActionEnum.Call:
            bounds = raise_bounds(self.state)
            action.amount = bounds.min_raise
            return action
        
        amount = action.amount
        decimal = amount - int(amount)
        divide = decimal / .25
        amount_of_quarters = round(divide)
        nearest_quarter_amount = int(amount) + (amount_of_quarters * .25)
        
        # make sure not raises go above max limit.
        bounds = raise_bounds(state=self.state)
        max_raise = bounds.max_raise
        while nearest_quarter_amount > max_raise:
            nearest_quarter_amount = nearest_quarter_amount -.25
            
        action.amount = nearest_quarter_amount
        print(f"Rounded {amount} to {nearest_quarter_amount}.")
        return action

    def handle_blind_stage(self):
        if self.n_players == 2:
            # Heads-up: button acts as small blind
            sb_pos = self.button_pos
            bb_pos = (self.button_pos + 1) % self.n_players
        else:
            sb_pos = (self.button_pos + 1) % self.n_players
            bb_pos = (self.button_pos + 2) % self.n_players

        # If an agent is posting a blind, dispense chips for it
        for idx, agent_pos in enumerate(self.agent_positions):
            agent_num = idx + 1
            if agent_pos == sb_pos:
                print(f"Agent {agent_num} (pos {agent_pos}) is small blind - dispensing")
                text_to_speech_hook(f"Agent {agent_num} (pos {agent_pos}) is small blind")
                
                dispense(num_dispensed=1, agent_num=agent_num)
                time.sleep(2)
            if agent_pos == bb_pos:
                print(f"Agent {agent_num} (pos {agent_pos}) is big blind - dispensing")
                text_to_speech_hook(f"Agent {agent_num} (pos {agent_pos}) is big blind")
                
                dispense(num_dispensed=2, agent_num=agent_num)
                time.sleep(2)
        for human_pos in enumerate(self.human_positions):
            if human_pos == sb_pos:
                print(f"Waiting for player {human_pos} to enter small blind amount. Press button when done.")
                text_to_speech_hook(f"Waiting for player {human_pos} to enter small blind amount. Press button when done.", skip=True)
                wait_for_player_action()
            if human_pos == bb_pos:
                print(f"Waiting for player {human_pos} to enter big blind amount. Press button when done.")
                text_to_speech_hook(f"Waiting for player {human_pos} to enter big blind amount. Press button when done.", skip=True)
                wait_for_player_action()
        # Tare after blind amounts are dispensed
        get_serial_pot_amount(tare=True, verbose=False)
        
    def set_agent_hand(self, agent_position: int, state:pkrs.State, temp_agent_num:int):
        """
        Sets the players_state of the agent's position to have the inputed cards
        
        Returns the state with the new agents's hand in place.
        """
        # grab cards from player input for now
        
        # Temporarliy hard coding ai cards. Used for testing
        #ai_hand = self.set_cards(count=4, camera_num=self.AGENT_HANDS_CAMERA_NUM, prompt=f"Scanning cards for agent position: {agent_position}")
        ai_hand = [Card.from_string("H2"), Card.from_string("S7"), Card.from_string("H2"), Card.from_string("S7")]
        # Assign state of this agent to have inputed cards as hand
        players_copy = state.players_state # players is a copy, must reasign
        ai_state = players_copy[agent_position]
        # agent 1 gets first two cards, agent 2 get second 2 cards
        if temp_agent_num == 1:
            ai_state.hand = (ai_hand[0], ai_hand[1])
        else: 
            ai_state.hand = (ai_hand[2], ai_hand[3])

        # Rewrite ai state in players
        players_copy[agent_position] = ai_state
        # Assign players back to original state
        state.players_state = players_copy
        
        return state

    def play_against_models_physical(self):
        """
        Play against models in a physical game setting.
            - Set button pos
            - Set flop, turn, and river cards
            - Set AI model's hands
            - Set each AI's initial stake
            - Set number of players and how many AI models there will be.
        """
        data = load_models_hook(self.n_players, self.num_agents)
        status = data["status"]
        print("load-models status: ", status)
        if status == "failed":
            raise Exception("Failed to load the models")

        num_games = 0
        total_profit = 0
        player_stake = self.initial_stake

        while True:
            # if player_stake <= 0:
            #     print("\nYou're out of chips! Game over.")
            #     break

            if num_games > 0:
                #choice = input("\nContinue playing? (y/n): ").strip().lower()
                # if choice != 'y':
                #     print("Thanks for playing!")
                #     break
                print("\nContinue Playing? Press any button to play again.")
                text_to_speech_hook("\nContinue Playing? Press any button to play again.", skip=True)
                wait_for_player_action()
            
            num_games += 1
            print(f"\n--- Game {num_games} ---")
            print(f"Your current balance: ${player_stake:.2f}")
            text_to_speech_hook(f"Game number {num_games}")
            
            # Updates agent bankrolls, humans stay at initial_stake.
            state = self.create_state()

            # for now there are only going to be 2 agents. The way I have the recognition 
            # model working is that it snaps a photo of all 4 cards at once. I am using a 
            # roundabout way to make sure the first agent gets the first 2 cards and the
            # second agent gets the third and fourth cards.
            print("Assigning agent hands..")
            text_to_speech_hook("Assigning agent hands")
            temp_agent_num = 1
            for agent_pos in self.agent_positions:
                state = self.set_agent_hand(agent_pos, state, temp_agent_num)
                temp_agent_num += 1
            
            print("Cards assigned to all players:")
            for position, player in enumerate(state.players_state):
                readable = [f"{card_to_string(card)}" for card in player.hand]
                print(f"Player {position}: {' '.join(readable)}")
            
            self.handle_blind_stage()

            community_cards = []
            current_stage = 0  # 0=PreFlop, 1=Flop, 2=Turn, 3=River, 4=Showdown
            while not state.final_state:
                # Detect stage transitions and prompt for new community cards
                new_stage = int(state.stage)
                if new_stage != current_stage:
                    if new_stage == 1:  # Flop
                        community_cards = self.set_cards(count=3, camera_num=self.COMMUNITY_CARDS_CAMERA_NUM, prompt="Enter the 3 FLOP cards")
                    elif new_stage == 2:  # Turn
                        turn = self.set_cards(count=4, camera_num=self.COMMUNITY_CARDS_CAMERA_NUM, prompt="Enter the TURN card")
                        community_cards = turn
                    elif new_stage == 3:  # River
                        river = self.set_cards(count=5, camera_num=self.COMMUNITY_CARDS_CAMERA_NUM, prompt="Enter the RIVER card")
                        community_cards = river
                    current_stage = new_stage

                if (current_stage != 0):
                    state.public_cards = community_cards
                
                current_player_pos = state.current_player
                action_with_rounded_amount = None
                # Display game state before human acts
                if current_player_pos in self.human_positions:
                    display_game_state(state, current_player_pos, human_positions=self.human_positions)
                    text_to_speech_hook(f"Player {current_player_pos}'s turn")
                    
                    
                    action = get_human_action_physical_game(state, current_player_pos)
                    action_with_rounded_amount = self.get_nearest_quarter_amount(action)
                    print(f"Player {current_player_pos} chose: {get_action_description(action_with_rounded_amount)}")
                    text_to_speech_hook(f"Player {current_player_pos} chose: {get_action_description(action_with_rounded_amount)}")
                    

                else:
                    display_game_state(state, current_player_pos, human_positions=self.human_positions)

                    # Abbreviated state display for AI turns
                    print(f"Player {current_player_pos}'s turn")
                    text_to_speech_hook(f"Player {current_player_pos}'s turn")
                    
                    
                    # self.agents is originally assigned agents based on pos
                    state_payload = create_state_json_payload(self.state, self.n_players, self.seed)
                    data = choose_action_hook(state_payload, current_player_pos)
                    
                    action_int = data["action"]
                    action_amount = data["amount"]
                    action = Action(self.action_enum_from_int(action_int), action_amount)
                    action_with_rounded_amount = self.get_nearest_quarter_amount(action)
                        
                    print(f"Player {current_player_pos} chose: {get_action_description(action)}")
                    text_to_speech_hook(f"Player {current_player_pos} chose: {get_action_description(action)}")

                    # only dispense for agents
                    agent_num = 1
                    if current_player_pos == 3:
                        agent_num = 2
                    num_chips_to_dispense = int(action_with_rounded_amount.amount / .25)
                    
                    if action_with_rounded_amount.action != pkrs.ActionEnum.Check and action_with_rounded_amount != pkrs.ActionEnum.Fold:
                        text_to_speech_hook(f"Dispensing {num_chips_to_dispense} chips", skip=True)
                        
                    dispense(num_dispensed=num_chips_to_dispense, agent_num=agent_num)
                    
                    # Tare after ai makes a move
                    get_serial_pot_amount(tare=True, verbose=False)

                # Apply the action
                new_state, log_file, status = apply_action_with_logging(
                    state,
                    action_with_rounded_amount
                )
                if new_state is None: # TODO: Figure out why state is returned as None when all ais folded. Or dont ig.
                    print(f"WARNING: State status not OK ({status}). Details logged to {log_file}")
                    break  # Skip this game in non-strict mode
                
                # make sure self.state is always the current game state (not too neccessary ig)
                self.state = new_state
                state = self.state
                
                # **** Game Loop Over **** #

            # Game is over, show results
            print("\n--- Game Over ---")
            
            # Show all players' hands
            print("Final hands:")
            for i, p in enumerate(state.players_state):
                # Check if the hand attribute exists and has cards
                if hasattr(p, 'hand') and p.hand:
                    hand = " ".join([card_to_string(card) for card in p.hand])
                    print(f"Player {i}: {hand}")
                else:
                    print(f"Player {i}: Hand data unavailable")
                        
            # Show community cards
            community_cards = " ".join([card_to_string(card) for card in state.public_cards])
            print(f"Community cards: {community_cards}")

            # Show results
            print("\nResults:")
            for i, p in enumerate(state.players_state):
                player_type = "YOU" if i in self.human_positions else "AI"
                print(f"Player {i} ({player_type}): ${p.reward:.2f}")

        # Show overall statistics
        print("\n--- Overall Statistics ---")
        print(f"Games played: {num_games}")
        print(f"Total profit: ${total_profit:.2f}")
        print(f"Average profit per game: ${total_profit/num_games if num_games > 0 else 0:.2f}")
        print(f"Final balance: ${player_stake:.2f}")
        
# $10 stake, 25 cent chips
if __name__ == "__main__":
    print("Making sure backend is running...")
    is_backend_up_hook()
    
    print("Performing homing sequences...")
    text_to_speech_hook("Performing homing sequences")
    
    # perform homing sequence for both dispensers before game starts
    # homing_sequence(1)
    # homing_sequence(2)
    
    print("Waiting for player action to start game...")
    text_to_speech_hook("Waiting for player action to start game", skip=True)
    wait_for_player_action()
    
    # move pot to low position to start game.
    #move_pot(high=False)
    
    print("Taring pot...")
    # double tare tech
    get_serial_pot_amount(tare=True)
    time.sleep(2)
    get_serial_pot_amount(tare=True)
    print("Taring done.")
    
    print("Waiting for arduino information")
    game_state = get_serial_gamestate_info(skip=True)
    
    PhysicalGame(
        n_players=game_state.num_players, 
        button_pos=game_state.button_pos, 
        initial_stake=game_state.initial_stake, 
        num_agents=game_state.num_agents, 
        small_blind=game_state.small_blind, 
        big_blind=game_state.big_blind
    ).play_against_models_physical()

# H2 S7 H2 S7