import torch
import os

from src.core.deep_cfr import DeepCFRAgent
from scripts.play import RandomAgent

class Agents:
    """
        Class to hold the DeepCFR agent models for the physical Texas Hold'em game.
    """
    
    def __init__(
        self,
        n_players,
        num_agents: int,
    ):
        self.n_players = n_players
        self.num_agents = num_agents
        
        self.agent_list = [None] * n_players
        self.num_human_players = n_players - num_agents
        self.agent_positions = list(
            range(self.num_human_players, n_players)
        )
        
    def load_agents(self):
        """
        Load AI agents into agent positions.
        """
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}")
        
        player_num_path = str(self.n_players) + "_player"
        
        base_path = f"models/standard/{player_num_path}/checkpoint_mixed"
        model_paths = [
            base_path + '/*checkpoint_iter_mixed_iter_33600.pt',
            base_path + '/*checkpoint_iter_mixed_iter_33700.pt',
            base_path + '/*checkpoint_iter_mixed_iter_33800.pt',
            base_path + '/*checkpoint_iter_mixed_iter_33900.pt',
            base_path + '/*checkpoint_iter_mixed_iter_400000.pt',
        ]

        print(f"Selected {len(model_paths)} models for this game:")
        for model_idx, path in enumerate(model_paths):
            print(f"  Model {model_idx+1}: {os.path.basename(path)}")

        # model_idx is its index in the model_paths list, pos is its position at the table
        for model_idx, pos in enumerate(self.agent_positions):
            if model_idx < len(model_paths):
                try:
                    agent = DeepCFRAgent(player_id=pos, num_players=self.n_players)
                    agent.load_model(model_paths[model_idx])
                    self.agent_list[pos] = agent
                    print(f"Loaded model for Player {pos}: {os.path.basename(model_paths[model_idx])}")
                except Exception as e:
                    print(f"Error loading model for Player {pos}: {e}")
                    return "failed"
            else:
                self.agent_list.append(RandomAgent(pos))
                print(f"Using random agent for Player {pos}")
        
        return "models loaded successfully"
