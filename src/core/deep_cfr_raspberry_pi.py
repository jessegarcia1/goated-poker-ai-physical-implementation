# deep_cfr.py
import numpy as np
import onnxruntime as ort
import pokers as pkrs
from src.core.model_raspberry_pi import encode_state
from src.utils.actions import (
    action_type_to_pokers_action as map_action_type_to_pokers_action,
    legal_action_types,
)

"""
    Stripped down version of the DeepCFRAgent class suited for raspberry pi.
    Changes:
        - torch has been replaced with onnxruntime. torch is too heavy of a download for the pi.
        - onnx is used for loading and querying the model, np used for softmax function.
        - Methods and fields unrelated for making decisions (e.g. training) have been removed
"""
class DeepCFRAgentRaspberryPi:
    def __init__(self, player_id=0, num_players=6, onnx_path=None):
        self.player_id = player_id
        self.num_players = num_players

        # Define action types (Fold, Check/Call, Raise)
        self.num_actions = 3

        # For keeping statistics
        self.iteration_count = 0

        # Bet sizing bounds (as multipliers of pot)
        self.min_bet_size = 0.1
        self.max_bet_size = 3.0

        # ONNX Runtime session for the strategy network (used for choosing actions)
        self.strategy_session = None
        if onnx_path is not None:
            self.load_model(onnx_path)

    def action_type_to_pokers_action(self, action_type, state, bet_size_multiplier=None):
        """
        Convert action type and optional bet size to Pokers action.
        """
        try:
            return map_action_type_to_pokers_action(
                action_type,
                state,
                bet_size_multiplier=bet_size_multiplier,
                min_bet_size=self.min_bet_size,
                max_bet_size=self.max_bet_size,
            )

        except Exception as e:
            print(f"DeepCFRAgent CRITICAL ERROR in action_type_to_pokers_action: Type {action_type} for player {self.player_id}: {e}")
            print(f"  State: current_player={state.current_player}, stage={state.stage}, legal_actions={state.legal_actions}")
            if hasattr(state, 'players_state') and self.player_id < len(state.players_state):
                print(f"  Player {self.player_id} stake: {state.players_state[self.player_id].stake}, bet: {state.players_state[self.player_id].bet_chips}")
            else:
                print(f"  Player state for player {self.player_id} not accessible.")
            import traceback
            traceback.print_exc()

            # Fall back to a safe action
            if hasattr(state, 'legal_actions'):
                if pkrs.ActionEnum.Call in state.legal_actions: return pkrs.Action(pkrs.ActionEnum.Call)
                if pkrs.ActionEnum.Check in state.legal_actions: return pkrs.Action(pkrs.ActionEnum.Check)
                if pkrs.ActionEnum.Fold in state.legal_actions: return pkrs.Action(pkrs.ActionEnum.Fold)
            
            # Absolute last resort if state.legal_actions is not even available or empty
            return pkrs.Action(pkrs.ActionEnum.Fold)

    def adjust_bet_size(self, state, base_multiplier):
        """
        Dynamically adjust bet size multiplier based on game state.
        
        Args:
            state: Current poker game state
            base_multiplier: Base bet size multiplier from the model
            
        Returns:
            Adjusted bet size multiplier
        """
        # Default adjustment factor
        adjustment = 1.0
        
        # Adjust based on game stage
        if int(state.stage) >= 2:  # Turn or River
            adjustment *= 1.2  # Increase bets in later streets
        
        # Adjust based on pot size relative to starting stack
        initial_stake = state.players_state[0].stake + state.players_state[0].bet_chips
        pot_ratio = state.pot / initial_stake
        if pot_ratio > 0.5:  # Large pot
            adjustment *= 1.1  # Bet bigger in large pots
        elif pot_ratio < 0.1:  # Small pot
            adjustment *= 0.9  # Bet smaller in small pots
        
        # Adjust based on position (more aggressive in late position)
        btn_distance = (state.current_player - state.button) % len(state.players_state)
        if btn_distance <= 1:  # Button or cutoff
            adjustment *= 1.15  # More aggressive in late position
        elif btn_distance >= 4:  # Early position
            adjustment *= 0.9  # Less aggressive in early position
        
        # Adjust for number of active players (larger with fewer players)
        active_players = sum(1 for p in state.players_state if p.active)
        if active_players <= 2:
            adjustment *= 1.2  # Larger bets heads-up
        elif active_players >= 5:
            adjustment *= 0.9  # Smaller bets multiway
        
        # Apply adjustment to base multiplier
        adjusted_multiplier = base_multiplier * adjustment
        
        # Ensure we stay within bounds
        return max(self.min_bet_size, min(self.max_bet_size, adjusted_multiplier))

    def get_legal_action_types(self, state):
        """Get the legal action types for the current state."""
        return legal_action_types(state)

    def choose_action(self, state):
        """Choose an action for the given state during actual play."""
        legal_action_types = self.get_legal_action_types(state)
        
        if not legal_action_types:
            # Default to call if no legal actions (shouldn't happen)
            if pkrs.ActionEnum.Call in state.legal_actions:
                return pkrs.Action(pkrs.ActionEnum.Call)
            elif pkrs.ActionEnum.Check in state.legal_actions:
                return pkrs.Action(pkrs.ActionEnum.Check)
            else:
                return pkrs.Action(pkrs.ActionEnum.Fold)

        encoded_state = encode_state(state, self.player_id).astype(np.float32)
        state_input = encoded_state.reshape(1, -1)

        input_name = self.strategy_session.get_inputs()[0].name
        logits, bet_size_pred = self.strategy_session.run(None, {input_name: state_input})

        # Softmax over logits (numpy equivalent of F.softmax(logits, dim=1))
        logits = logits[0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        bet_size_multiplier = float(bet_size_pred[0][0])
        
        # Filter to only legal actions
        legal_probs = np.array([probs[a] for a in legal_action_types])
        if np.sum(legal_probs) > 0:
            legal_probs = legal_probs / np.sum(legal_probs)
        else:
            legal_probs = np.ones(len(legal_action_types)) / len(legal_action_types)
        
        # Choose action based on probabilities
        action_idx = np.random.choice(len(legal_action_types), p=legal_probs)
        action_type = legal_action_types[action_idx]
        
        # Use the predicted bet size for raise actions
        if action_type == 2:  # Raise
            return self.action_type_to_pokers_action(action_type, state, bet_size_multiplier)
        else:
            return self.action_type_to_pokers_action(action_type, state)

    def load_model(self, path):
        """Load the ONNX strategy model for inference."""
        self.strategy_session = ort.InferenceSession(path, providers=['CPUExecutionProvider'])