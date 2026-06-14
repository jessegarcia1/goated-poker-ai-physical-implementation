import torch
import pokers as pkrs
import random
import os
import numpy as np

from pokers import Card, Action
from src.core.deep_cfr import DeepCFRAgent
from scripts.play import RandomAgent, get_human_action, display_game_state, get_action_description, log_game_error, card_to_string, set_verbose

"""
    To run: python -m scripts.play_physical 
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
        num_human_players: int,
        num_agents: int,
        small_blind: float = 1.0,
        big_blind: float = 2.0,
        verbose: bool = False,
    ):
        if num_human_players + num_agents != n_players:
            raise ValueError("num_human_players + num_agents must equal n_players")

        if n_players <= 1:
            raise ValueError("Need at least 2 players")
        
        self.n_players = n_players
        self.button_pos = button_pos
        self.initial_stake = initial_stake
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.verbose = verbose
        self.num_human_players = num_human_players
        self.num_agents = num_agents

        # Humans occupy first N seats by default
        self.human_positions = list(range(num_human_players))
        # Agents occupy remaining seats
        self.agent_positions = list(
            range(num_human_players, n_players)
        )

        # Bankroll tracking
        self.player_stakes = {
            player_id: initial_stake
            for player_id in range(n_players)
        }
        
        self.state = None
        self.agents = [None] * n_players
        self.device = (
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"Using device: {self.device}")

    def load_agents(self, model_paths):
        """
        Load AI agents into agent positions.
        """
        print(f"Selected {len(model_paths)} models for this game:")
        for model_idx, path in enumerate(model_paths):
            print(f"  Model {model_idx+1}: {os.path.basename(path)}")
        set_verbose(self.verbose)

        # model_idx is its index in the model_paths list, pos is its position at the table
        for model_idx, pos in enumerate(self.agent_positions):
            if model_idx < len(model_paths):
                try:
                    agent = DeepCFRAgent(player_id=pos, num_players=self.n_players, device=self.device)
                    agent.load_model(model_paths[model_idx])
                    self.agents[pos] = agent
                    print(f"Loaded model for Player {pos}: {os.path.basename(model_paths[model_idx])}")
                except Exception as e:
                    print(f"Error loading model for Player {pos}: {e}")
                    self.agents.append(RandomAgent(pos))
            else:
                self.agents.append(RandomAgent(pos))
                print(f"Using random agent for Player {pos}")

    def create_state(self):
        """
        Create a new poker state using current bankrolls.
        """        
        self.state = pkrs.State.from_seed(
            n_players=self.n_players,
            button=self.button_pos,
            sb=self.small_blind,
            bb=self.big_blind,
            stake=self.initial_stake,
            seed=random.randint(0, 10000),
        )

        # Manually overwrite player stakes, ai stakes will be tracked and updated.
        # Human stakes will always be the initial_stake becausee these cannot be tracked.
        players = self.state.players_state # players is a copy of players_state
        for player_id, player_state in enumerate(players):
            if player_id in self.agent_positions:
                player_state.stake = self.player_stakes[player_id]
                players[player_id] = player_state
            else:
                print(f"Skipped overwriting stake for player number {player_id}")

        self.state.players_state = players

        return self.state

    def set_cards(self, prompt, count):
        """
        Prompt the user to enter cards from the physical table.
        
        Args:
            prompt: Description of which cards to enter
            count: How many cards to enter
        Returns:
            List of parsed card dicts
        """    
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
            if confirm == 'y':
                print("\n")
                return card_objects

    def get_nearest_quarter_amount(self, action: Action):
        """
        Rounds the amount of the action to the nearest .25 cents.
        """
        amount = action.amount
        decimal = amount - int(amount)
        divide = decimal / .25
        amount_of_quarters = round(divide)
        nearest_quarter_amount = int(amount) + (amount_of_quarters * 3)
        action.amount = nearest_quarter_amount
        return action
        
    def set_agent_hand(self, agent_position: int, state:pkrs.State, image: np.ndarray=None):
        """
        Sets the players_state of the agent's position to have the inputed cards
        
        Returns the state with the new agents's hand in place.
        """
        # grab cards from player input for now
        # ai_hand = self.set_cards(f"Enter the AI's hole cards (Player {agent_position})", 2)
        ai_hand = [Card.from_string("C5"), Card.from_string("CT")]
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

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}")
        
        base_path = 'models/mixed'
        model_paths = [
            base_path + '/mixed_checkpoint_iter_1600.pt',
            base_path + '/mixed_checkpoint_iter_1500.pt',
            base_path + '/mixed_checkpoint_iter_1400.pt',
            base_path + '/mixed_checkpoint_iter_1300.pt',
            'models/selfplay' + '/selfplay_checkpoint_iter_2000.pt'
        ]
        
        self.load_agents(model_paths=model_paths)

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
                        community_cards = self.set_cards("Enter the 3 FLOP cards", 3)
                    elif new_stage == 2:  # Turn
                        turn = self.set_cards("Enter the TURN card", 1)
                        community_cards = community_cards + turn
                    elif new_stage == 3:  # River
                        river = self.set_cards("Enter the RIVER card", 1)
                        community_cards = community_cards + river
                    current_stage = new_stage

                current_player_pos = state.current_player
                if (current_stage != 0):
                    state.public_cards = community_cards
                
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

                rounded_action_amount = self.get_nearest_quarter_amount(action)
                # Apply the action
                new_state = state.apply_action(rounded_action_amount)
                if new_state.status != pkrs.StateStatus.Ok:
                    log_file = log_game_error(state, rounded_action_amount, f"State status not OK ({new_state.status})")
                    print(f"WARNING: State status not OK ({new_state.status}). Details logged to {log_file}")
                    break
                state = new_state

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

            # Update player's stake
            # game_profit = state.players_state[player_position].reward
            # total_profit += game_profit
            # player_stake += game_profit

            # print(f"\nThis game: {'Won' if game_profit > 0 else 'Lost'} ${abs(game_profit):.2f}")
            # print(f"Running total: ${total_profit:.2f}")
            # print(f"Current balance: ${player_stake:.2f}")

        # Show overall statistics
        print("\n--- Overall Statistics ---")
        print(f"Games played: {num_games}")
        print(f"Total profit: ${total_profit:.2f}")
        print(f"Average profit per game: ${total_profit/num_games if num_games > 0 else 0:.2f}")
        print(f"Final balance: ${player_stake:.2f}")
        
# Same as default settings
PhysicalGame(n_players=6, button_pos=1, initial_stake=10.0, num_human_players=3, num_agents=3, small_blind=.25, big_blind=.50).play_against_models_physical()