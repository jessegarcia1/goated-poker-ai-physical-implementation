import pokers as pkrs
import random
import requests
import time

from pokers import Card, Action, State
from scripts.play_helpers import card_to_string, get_action_description, get_human_action, display_game_state
from src.utils import apply_action_with_logging
from src.utils.raspi import capture_photo, get_serial_info
from src.routes.routes import urls, routes
from src.utils.actions import raise_bounds

"""
    To run: python3 -m scripts.play_physical 
    Players 4 and five are lowkey special
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
        
    def handle_post_request(self, payload: dict, route_key: str, timeout: float = 10.0):
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
            raise Exception("Post request receives status of 204, response = { }")

        try:
            return response.json()
        except ValueError as err:
            print(f"Failed to parse JSON response from {url}: {err}")
            raise

    def create_state(self):
        """
            Create a new poker state using current bankrolls.
        """        
        print("debug")
        print(type(self.n_players))
        print(type(self.button_pos))
        print(type(self.small_blind))
        print(type(self.big_blind))
        print(type(self.initial_stake))
        
        self.state = State.from_seed(
            n_players=self.n_players,
            button=self.button_pos,
            sb=self.small_blind,
            bb=self.big_blind,
            stake=self.initial_stake,
            seed=random.randint(0, 10000),
        )

        print("Debug")
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

    def set_cards(self, count: int, prompt: str=None, detect=True)-> list[Card] | None:
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
                image = capture_photo(0)
                payload = {"image_as_list": image, "count": count}
                
                print('Sending photo...\n')
                data = self.handle_post_request(payload, "card-detection")

                status = data["status"]
                print("detection status: ", status)
                
                if status == "ok":
                    return data["card_list"]
                
            raise Exception(f"ERROR: {count} Cards failed to be set.")

    def get_nearest_quarter_amount(self, action: Action):
        """
        Rounds the amount of the action to the nearest .25 cents. Always rounds down
        """
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
        
    def set_agent_hand(self, agent_position: int, state:pkrs.State):
        """
        Sets the players_state of the agent's position to have the inputed cards
        
        Returns the state with the new agents's hand in place.
        """
        # grab cards from player input for now
        ai_hand = self.set_cards(2, f"Enter hand for agent position: {agent_position}")
        # Assign state of this agent to have inputed cards as hand
        players_copy = state.players_state # players is a copy, must reasign
        ai_state = players_copy[agent_position]
        ai_state.hand = (ai_hand[0], ai_hand[1])
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
        
        payload = {"n_players": self.n_players, "n_agents": self.num_agents}

        data = self.handle_post_request(payload, "load-models")
        status = data["status"]
        print("status: ", status)
        if status == "failed":
            raise Exception("Failed loading models")

        num_games = 0
        total_profit = 0
        player_stake = self.initial_stake

        while True:
            if player_stake <= 0:
                print("\nYou're out of chips! Game over.")
                break

            if num_games > 0:
                choice = input("\nContinue playing? (y/n): ").strip().lower()
                if choice != 'y':
                    print("Thanks for playing!")
                    break
            
            num_games += 1
            print(f"\n--- Game {num_games} ---")
            print(f"Your current balance: ${player_stake:.2f}")
            
            # Updates agent bankrolls, humans stay at initial_stake.
            state = self.create_state()
            print(f"State created: {state}")

            # Collect physical cards before betting starts
            # if num_ai != len(image_list):
            #     print(f"The number of ai models, {num_ai} does not match the amount of images given: {len(image_list)}")
            #     raise ValueError("Number of models does not match with number of images in set_ai_hands.")
            for agent_pos in self.agent_positions:
                state = self.set_agent_hand(agent_pos, state)
            
            print("Cards assigned to all players:")
            for position, player in enumerate(state.players_state):
                readable = [f"{card_to_string(card)}" for card in player.hand]
                print(f"Player {position}: {' '.join(readable)}")

            community_cards = []
            current_stage = 0  # 0=PreFlop, 1=Flop, 2=Turn, 3=River, 4=Showdown
            while not state.final_state:
                # Detect stage transitions and prompt for new community cards
                new_stage = int(state.stage)
                if new_stage != current_stage:
                    if new_stage == 1:  # Flop
                        community_cards = self.set_cards(3, "Enter the 3 FLOP cards", )
                    elif new_stage == 2:  # Turn
                        turn = self.set_cards(1, "Enter the TURN card")
                        community_cards = community_cards + turn
                    elif new_stage == 3:  # River
                        river = self.set_cards(1, "Enter the RIVER card")
                        community_cards = community_cards + river
                    current_stage = new_stage

                if (current_stage != 0):
                    state.public_cards = community_cards
                
                current_player_pos = state.current_player
                # Display game state before human acts
                if current_player_pos in self.human_positions:
                    display_game_state(state, current_player_pos, human_positions=self.human_positions)
                    action = get_human_action(state, current_player_pos)
                    print(f"You chose: {get_action_description(action)}")
                else:
                    # Abbreviated state display for AI turns
                    print(f"\nPlayer {current_player_pos}'s turn")
                    # self.agents is originally assigned agents based on pos
                    agent = self.agents[current_player_pos]
                    if agent is None:
                        raise RuntimeError(f"No agent loaded for player {current_player_pos}")
                    action = agent.choose_action(state) 
                    print(f"Player {current_player_pos} chose: {get_action_description(action)}")

                action_with_rounded_amount = self.get_nearest_quarter_amount(action)
                
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
    print("Sending get request...")
    r = requests.get(urls["mac-tailscale-ip"] + routes["is-backend-up"])

    if (r.status_code != 200):
        raise Exception("Backend is not up!")
    
    print("Waiting for arduino information")
    game_state = get_serial_info(skip=True)
        
    PhysicalGame(
        n_players=game_state.num_players, 
        button_pos=game_state.button_pos, 
        initial_stake=game_state.initial_stake, 
        num_agents=game_state.num_agents, 
        small_blind=game_state.small_blind, 
        big_blind=game_state.big_blind
    ).play_against_models_physical()