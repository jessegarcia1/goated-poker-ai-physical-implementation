#play_helpers.py
import pokers as pkrs
import time

from src.utils.actions import build_raise_action, preset_raise_action, raise_bounds
from scripts.raspi_gpio_scripts.get_player_action import wait_for_player_action
from src.utils.raspi import get_serial_pot_amount

def get_action_description(action):
    """Convert a pokers action to a human-readable string."""
    if action.action == pkrs.ActionEnum.Fold:
        return "Fold"
    elif action.action == pkrs.ActionEnum.Check:
        return "Check"
    elif action.action == pkrs.ActionEnum.Call:
        return "Call"
    elif action.action == pkrs.ActionEnum.Raise:
        return f"Raise to {action.amount:.2f}"
    else:
        return f"Unknown action: {action.action}"

def card_to_string(card):
    """Convert a poker card to a readable string."""
    suits = {0: "♣", 1: "♦", 2: "♥", 3: "♠"}
    ranks = {0: "2", 1: "3", 2: "4", 3: "5", 4: "6", 5: "7", 6: "8", 
             7: "9", 8: "10", 9: "J", 10: "Q", 11: "K", 12: "A"}
    
    return f"{ranks[int(card.rank)]}{suits[int(card.suit)]}"

def display_game_state(state, player_id=0, human_positions=None):
    """Display the current game state in a human-readable format."""
    print("\n" + "="*70)
    
    # Fix for Stage enum - convert to string properly
    stage_names = {
        0: "PreFlop",
        1: "Flop", 
        2: "Turn", 
        3: "River", 
        4: "Showdown"
    }
    stage_name = stage_names.get(int(state.stage), str(state.stage))
    print(f"Stage: {stage_name}")
    
    print(f"Pot: ${state.pot:.2f}")
    print(f"Button position: Player {state.button}")
    
    # Show community cards
    community_cards = " ".join([card_to_string(card) for card in state.public_cards])
    print(f"Community cards: {community_cards if community_cards else 'None'}")
    
    # Show player's hand
    hand = " ".join([card_to_string(card) for card in state.players_state[player_id].hand])
    print(f"Your hand: {hand}")
    
    # Show all players' states
    print("\nPlayers:")
    for i, p in enumerate(state.players_state):
        status = "HUMAN" if i in human_positions else "AI"
        if (i == player_id):
            status = "YOU"
        active = "Active" if p.active else "Folded"
        print(f"Player {i} ({status}): ${p.stake:.2f} - Bet: ${p.bet_chips:.2f} - {active}")
    
    # Show legal actions for human player if it's their turn
    if state.current_player == player_id:
        print("\nLegal actions:")
        for action_enum in state.legal_actions:
            if action_enum == pkrs.ActionEnum.Fold:
                print("  f: Fold")
            elif action_enum == pkrs.ActionEnum.Check:
                print("  c: Check")
            elif action_enum == pkrs.ActionEnum.Call:
                # Calculate call amount
                call_amount = max(0, state.min_bet - state.players_state[player_id].bet_chips)
                print(f"  c: Call ${call_amount:.2f}")
            elif action_enum == pkrs.ActionEnum.Raise:
                bounds = raise_bounds(state)
                print(f"  r: Raise (min: ${bounds.min_raise:.2f}, max: ${bounds.max_raise:.2f})")
                print("    h: Raise half pot")
                print("    p: Raise pot")
                print("    m: Custom raise amount")
    
    print("="*70)

def get_human_action(state, player_id=0):
    """Get action from human player via console input."""
    while True:
        action_input = input("Your action (f=fold, c=check/call, r=raise, h=half pot, p=pot, m=custom): ").strip().lower()
        
        # Process fold
        if action_input == 'f' and pkrs.ActionEnum.Fold in state.legal_actions:
            return pkrs.Action(pkrs.ActionEnum.Fold)
        
        # Process check/call
        elif action_input == 'c':
            if pkrs.ActionEnum.Check in state.legal_actions:
                return pkrs.Action(pkrs.ActionEnum.Check)
            elif pkrs.ActionEnum.Call in state.legal_actions:
                return pkrs.Action(pkrs.ActionEnum.Call)
        
        # Process raise shortcuts
        elif action_input in ['r', 'h', 'p', 'm'] and pkrs.ActionEnum.Raise in state.legal_actions:
            bounds = raise_bounds(state)

            if not bounds.can_raise:
                print("You don't have enough chips to raise. Calling instead.")
                return pkrs.Action(pkrs.ActionEnum.Call)

            if action_input == 'h':  # Half pot
                return preset_raise_action(state, "half_pot")

            elif action_input == 'p':  # Full pot
                return preset_raise_action(state, "pot")

            elif action_input == 'm' or action_input == 'r':  # Custom amount
                while True:
                    try:
                        amount_str = input(f"Enter raise amount (min: {bounds.min_raise:.2f}, max: {bounds.max_raise:.2f}): ")
                        amount = float(amount_str)

                        if bounds.min_raise <= amount <= bounds.max_raise:
                            return build_raise_action(state, amount)
                        else:
                            print(f"Amount must be between {bounds.min_raise:.2f} and {bounds.max_raise:.2f}")
                    except ValueError:
                        print("Please enter a valid number")
        
        print("Invalid action. Please try again.")
        
def get_human_action_physical_game(state, player_id:int=0):
    """Get action from human player via console input."""
    
    while True:
        action_input = wait_for_player_action()
        print(state.legal_actions)
        # Process fold
        if action_input == 'fold' and pkrs.ActionEnum.Fold in state.legal_actions:
            return pkrs.Action(pkrs.ActionEnum.Fold)
        
        # Process check/call
        elif action_input == 'check':
            if pkrs.ActionEnum.Check in state.legal_actions:
                # tare after a call
                get_serial_pot_amount(tare=True) 
                
                return pkrs.Action(pkrs.ActionEnum.Check)
            elif pkrs.ActionEnum.Call in state.legal_actions:
                # tare after a call
                get_serial_pot_amount(tare=True) 
                
                return pkrs.Action(pkrs.ActionEnum.Call)
        
        # Process raise. Player will always add their chips to the pot, then press the button
        elif action_input == 'raise' and pkrs.ActionEnum.Raise in state.legal_actions:
            bounds = raise_bounds(state)
            chips_raised = get_serial_pot_amount()
            amount = chips_raised * .25
            if bounds.min_raise <= amount <= bounds.max_raise:
                return build_raise_action(state, amount)
            else:
                print(f"Amount must be between {bounds.min_raise:.2f} and {bounds.max_raise:.2f}")
        
        print("Invalid action. Please Enter your action again.")
        
        # tare after invalid action
        get_serial_pot_amount(tare=True)
        