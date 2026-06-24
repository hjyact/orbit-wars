import json
from pathlib import Path

REPLAY_PATH = Path("/home/hjyact/GitHub/Orbit_Wars/top_replays/episode-81068450-replay.json")

def main():
    if not REPLAY_PATH.exists():
        # find any json in the top_replays dir
        dir_files = list(Path("/home/hjyact/GitHub/Orbit_Wars/top_replays").glob("*.json"))
        if not dir_files:
            print("No replay files found")
            return
        replay_path = dir_files[0]
    else:
        replay_path = REPLAY_PATH

    print(f"Reading {replay_path}")
    with open(replay_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("Keys in replay file:", list(data.keys()))
    steps = data.get("steps", [])
    print(f"Number of steps: {len(steps)}")
    
    if len(steps) > 1:
        # Find a step where at least one player has fleets
        found = False
        for step_idx in range(1, len(steps)):
            step_data = steps[step_idx]
            for player_idx, player_state in enumerate(step_data):
                if player_state:
                    obs = player_state.get("observation", {})
                    fleets = obs.get("fleets", [])
                    if len(fleets) > 0:
                        print(f"\n--- Found fleets at Step {step_idx}, Player {player_idx} ---")
                        print(f"Observation keys: {list(obs.keys())}")
                        print(f"Number of fleets: {len(fleets)}")
                        print(f"Sample fleet: {fleets[0]}")
                        
                        planets = obs.get("planets", [])
                        print(f"Number of planets: {len(planets)}")
                        print(f"Sample planet: {planets[0]}")
                        
                        print(f"Action taken in step: {player_state.get('action')}")
                        found = True
                        break
            if found:
                break


if __name__ == "__main__":
    main()
