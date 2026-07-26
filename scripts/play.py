#play.py
import pokers as pkrs
import torch
import numpy as np
import argparse
import os
import random
import glob
from src.core.deep_cfr import DeepCFRAgent
from src.core.model import set_verbose
from src.utils import apply_action_with_logging
from src.utils.actions import build_raise_action, preset_raise_action, raise_bounds
from src.utils.settings import STRICT_CHECKING, set_strict_checking
from scripts.play_helpers import get_action_description, card_to_string, display_game_state, get_human_action

def select_random_models(models_dir, num_models=5, model_pattern="*.pt"):
    """
    Select random model checkpoint files from a directory.
    
    Args:
        models_dir: Directory containing model checkpoint files
        num_models: Number of models to select
        model_pattern: File pattern to match model files
        
    Returns:
        List of paths to selected model files
    """
    # Get all model checkpoint files in the directory
    model_files = glob.glob(os.path.join(models_dir, model_pattern))
    
    if not model_files:
        print(f"No model files found in {models_dir} matching pattern '{model_pattern}'")
        return []
    
    # Select random models
    selected_models = random.sample(model_files, min(num_models, len(model_files)))
    return selected_models

def play_against_models(models_dir=None, model_pattern="*.pt", num_models=5, 
                        player_position=0, initial_stake=200.0, small_blind=1.0, 
                        big_blind=2.0, verbose=False, shuffle_models=True):
    """
    Play against randomly selected AI models from a directory.
    
    Args:
        models_dir: Directory containing model checkpoint files
        model_pattern: File pattern to match model files
        num_models: Number of models to select
        player_position: Position of the human player (0-5)
        initial_stake: Starting chip count for all players
        small_blind: Small blind amount
        big_blind: Big blind amount
        verbose: Whether to show detailed output
        shuffle_models: Whether to select new random models for each game
    """
    set_verbose(verbose)
    
    # Check if models directory exists
    if models_dir and not os.path.isdir(models_dir):
        print(f"Warning: Models directory {models_dir} not found.")
        models_dir = None
    
    # Device configuration
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    # Track game statistics
    num_games = 0
    total_profit = 0
    player_stake = initial_stake
    
    # Main game loop
    while True:
        if player_stake <= 0:
            print("\nYou're out of chips! Game over.")
            break
        
        # Ask if player wants to continue after the first game
        if num_games > 0:
            choice = input("\nContinue playing? (y/n): ").strip().lower()
            if choice != 'y':
                print("Thanks for playing!")
                break
        
        # Select new random models for this game if shuffling is enabled or first game
        if (shuffle_models or num_games == 0) and models_dir:
            model_paths = select_random_models(models_dir, num_models, model_pattern)
            print(f"Selected {len(model_paths)} random models for this game:")
            for i, path in enumerate(model_paths):
                print(f"  Model {i+1}: {os.path.basename(path)}")
        elif not models_dir:
            model_paths = []
            print("No models directory specified, using random agents.")
        
        # Create agents for each position
        agents = []
        for i in range(6):
            if i == player_position:
                # Human player
                agents.append(None)
            else:
                # Determine which model to use
                model_idx = (i - 1) if i > player_position else i
                if models_dir and model_idx < len(model_paths):
                    # Load model
                    try:
                        agent = DeepCFRAgent(player_id=i, num_players=6, device=device)
                        agent.load_model(model_paths[model_idx])
                        agents.append(agent)
                        print(f"Loaded model for Player {i}: {os.path.basename(model_paths[model_idx])}")
                    except Exception as e:
                        print(f"Error loading model for Player {i}: {e}")
                        print("Using random agent instead")
                        agents.append(RandomAgent(i))
                else:
                    # Use random agent
                    agents.append(RandomAgent(i))
                    print(f"Using random agent for Player {i}")
        
        num_games += 1
        print(f"\n--- Game {num_games} ---")
        print(f"Your current balance: ${player_stake:.2f}")
        
        # Rotate button position for fairness
        button_pos = (num_games - 1) % 6
        
        # Create a new poker game
        state = pkrs.State.from_seed(
            n_players=6,
            button=button_pos,
            sb=small_blind,
            bb=big_blind,
            stake=initial_stake,
            seed=random.randint(0, 10000)
        )
        
        # Play until the game is over
        while not state.final_state:
            current_player = state.current_player
            
            # Display game state before human acts
            if current_player == player_position:
                display_game_state(state, player_position)
                action = get_human_action(state, player_position)
                print(f"You chose: {get_action_description(action)}")
            else:
                # Abbreviated state display for AI turns
                print(f"\nPlayer {current_player}'s turn")
                action = agents[current_player].choose_action(state)
                print(f"Player {current_player} chose: {get_action_description(action)}")
            
            # Apply the action
            new_state, log_file, status = apply_action_with_logging(
                state,
                action,
                strict=STRICT_CHECKING,
            )
            if new_state is None:
                print(f"WARNING: State status not OK ({status}). Details logged to {log_file}")
                break  # Skip this game in non-strict mode
            
            state = new_state
        
        # Game is over, show results
        print("\n--- Game Over ---")
        
        # Show all players' hands
        print("Final hands:")
        for i, p in enumerate(state.players_state):
            if p.active:
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
            player_type = "YOU" if i == player_position else "AI"
            print(f"Player {i} ({player_type}): ${p.reward:.2f}")
        
        # Update player's stake
        game_profit = state.players_state[player_position].reward
        total_profit += game_profit
        player_stake += game_profit
        
        print(f"\nThis game: {'Won' if game_profit > 0 else 'Lost'} ${abs(game_profit):.2f}")
        print(f"Running total: ${total_profit:.2f}")
        print(f"Current balance: ${player_stake:.2f}")
    
    # Show overall statistics
    print("\n--- Overall Statistics ---")
    print(f"Games played: {num_games}")
    print(f"Total profit: ${total_profit:.2f}")
    print(f"Average profit per game: ${total_profit/num_games if num_games > 0 else 0:.2f}")
    print(f"Final balance: ${player_stake:.2f}")

class RandomAgent:
    """Simple random agent for poker that ensures valid bet sizing."""
    def __init__(self, player_id):
        self.player_id = player_id
        
    def choose_action(self, state):
        """Choose a random legal action with correctly calculated bet sizing."""
        if not state.legal_actions:
            raise ValueError(f"No legal actions available for player {self.player_id}")
        
        # Select a random legal action
        action_enum = random.choice(state.legal_actions)
        
        # For fold, check, and call, no amount is needed
        if action_enum == pkrs.ActionEnum.Fold:
            return pkrs.Action(action_enum)
        elif action_enum == pkrs.ActionEnum.Check:
            return pkrs.Action(action_enum)
        elif action_enum == pkrs.ActionEnum.Call:
            return pkrs.Action(action_enum)
        # For raises, carefully calculate a valid amount
        elif action_enum == pkrs.ActionEnum.Raise:
            return preset_raise_action(
                state,
                random.choice(["min", "half_pot", "pot", "all_in"]),
            )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Play poker against random AI models')
    parser.add_argument('--models-dir', type=str, default=None, help='Directory containing model checkpoint files')
    parser.add_argument('--model-pattern', type=str, default="*.pt", help='File pattern to match model files')
    parser.add_argument('--num-models', type=int, default=5, help='Number of models to select')
    parser.add_argument('--position', type=int, default=0, help='Your position at the table (0-5)')
    parser.add_argument('--stake', type=float, default=200.0, help='Initial stake')
    parser.add_argument('--sb', type=float, default=1.0, help='Small blind amount')
    parser.add_argument('--bb', type=float, default=2.0, help='Big blind amount')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    parser.add_argument('--no-shuffle', action='store_true', help='Do not select new random models for each game')
    parser.add_argument('--strict', action='store_true', help='Enable strict error checking that raises exceptions for invalid game states')
    args = parser.parse_args()
    
    set_strict_checking(args.strict)

    # Start the game
    play_against_models(
        models_dir=args.models_dir,
        model_pattern=args.model_pattern,
        num_models=args.num_models,
        player_position=args.position,
        initial_stake=args.stake,
        small_blind=args.sb,
        big_blind=args.bb,
        verbose=args.verbose,
        shuffle_models=not args.no_shuffle
    )