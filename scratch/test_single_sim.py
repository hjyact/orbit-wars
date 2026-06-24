import sys
import os
import torch

sys.path.insert(0, "/home/hjyact/GitHub/Orbit_Wars")
sys.path.insert(0, "/home/hjyact/GitHub/Orbit_Wars/scratch")

from rl_training_restored.train_selfplay_rl_features import run_match_worker, ImitationMLPFeatures

# Load 2p weights
weights_path = "/home/hjyact/GitHub/Orbit_Wars/scratch/imitation_weights_features_2p.pt"
if not os.path.exists(weights_path):
    print("Error: 2P weights not found!")
    sys.exit(1)

model = ImitationMLPFeatures()
model_weights = torch.load(weights_path, map_location="cpu")
model.load_state_dict(model_weights)
weights_cpu = {k: v.cpu() for k, v in model.state_dict().items()}

# Set up tasks
seed = 42
p1_path = "trainable"
p2_path = "selfplay"
tau = 1.0
is_eval = False

print("Starting single simulation test...")
res = run_match_worker((seed, p1_path, p2_path, weights_cpu, tau, is_eval))
print("Simulation result:")
print(res)
