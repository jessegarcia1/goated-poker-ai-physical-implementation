"""
Core models and neural network utilities for the DeepCFR Poker AI.
"""

try:
    from .model import PokerNetwork, encode_state, set_verbose
    from .deep_cfr import DeepCFRAgent
    __all__ = ['PokerNetwork', 'encode_state', 'set_verbose', 'DeepCFRAgent']
except ImportError:
    # for when torch isn't available on raspberry pi
    from .model_raspberry_pi import PokerNetworkRaspberryPi, encode_state, set_verbose
    from .deep_cfr_raspberry_pi import DeepCFRAgentRaspberryPi
    __all__ = ['PokerNetworkRaspberryPi, encode_state', 'set_verbose', 'DeepCFRAgentRaspberryPi']