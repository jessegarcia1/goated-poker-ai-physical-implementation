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
        print("agent_pos: ", self.agent_positions)
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}")
        
        player_num_path = str(self.n_players) + "_player"
        
        # base_path = f"models/standard/{player_num_path}/mixed"
        # potential_model_paths = [
        #     base_path + '/mixed_checkpoint_iter_36000.pt',
        #     base_path + '/mixed_checkpoint_iter_37000.pt',
        #     base_path + '/mixed_checkpoint_iter_38000.pt',
        #     base_path + '/mixed_checkpoint_iter_39000.pt',
        #     base_path + '/mixed_checkpoint_iter_40000.pt',
        # ]
        
        base_path = f"models/standard/{player_num_path}/selfplay_from_20000"
        potential_model_paths = [
            base_path + '/selfplay_checkpoint_iter_26000.pt',
            base_path + '/selfplay_checkpoint_iter_27000.pt',
            base_path + '/selfplay_checkpoint_iter_28000.pt',
            base_path + '/selfplay_checkpoint_iter_29000.pt',
            base_path + '/selfplay_checkpoint_iter_30000.pt',
        ]
        
        # base_path = f"models/standard/{player_num_path}/phase1_20k"
        # potential_model_paths = [
        #     base_path + '/checkpoint_iter_16000.pt',
        #     base_path + '/checkpoint_iter_17000.pt',
        #     base_path + '/checkpoint_iter_18000.pt',
        #     base_path + '/checkpoint_iter_19000.pt',
        #     base_path + '/checkpoint_iter_20000.pt',
        # ]

        # get get only 'num_agents' number of model paths
        model_paths = potential_model_paths[:self.num_agents]

        print(f"Selected {self.num_agents} models for this game:")
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
