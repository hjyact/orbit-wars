import sys
import os
import argparse
from kaggle_environments import make

def main():
    parser = argparse.ArgumentParser(description="Run Orbit Wars locally.")
    parser.add_argument("--p1", type=str, default="main.py", help="Path to player 1 agent Python script (or 'random', 'starter')")
    parser.add_argument("--p2", type=str, default="main.py", help="Path to player 2 agent Python script (or 'random', 'starter')")
    parser.add_argument("--p3", type=str, default=None, help="Path to player 3 agent (optional for 4-player FFA)")
    parser.add_argument("--p4", type=str, default=None, help="Path to player 4 agent (optional for 4-player FFA)")
    parser.add_argument("--out", type=str, default="replay.html", help="Path to save the HTML replay")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode in kaggle-environments")
    args = parser.parse_args()

    # Load agents
    agents = []
    player_paths = [args.p1, args.p2]
    if args.p3:
        player_paths.append(args.p3)
    if args.p4:
        player_paths.append(args.p4)

    print("Loading agents...")
    for idx, path in enumerate(player_paths):
        if path in ["random", "starter"]:
            agents.append(path)
            print(f"  Player {idx+1}: built-in '{path}'")
        else:
            # We can import the agent from the file path
            # To handle local relative imports inside the agent file, we insert its directory into sys.path
            abs_path = os.path.abspath(path)
            dir_name = os.path.dirname(abs_path)
            if dir_name not in sys.path:
                sys.path.insert(0, dir_name)
            
            # Use importlib to dynamically load the agent
            import importlib.util
            module_name = f"agent_{idx}"
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            if hasattr(module, "agent"):
                agents.append(module.agent)
                print(f"  Player {idx+1}: loaded 'agent' from {path}")
            else:
                raise AttributeError(f"The agent script {path} does not define an 'agent' function.")

    print(f"Initializing Orbit Wars environment ({len(agents)} players)...")
    env = make("orbit_wars", debug=args.debug)
    
    print("Running match...")
    env.run(agents)
    
    print(f"Match finished! Total steps: {len(env.steps)}")
    
    # Save replay
    print(f"Saving visual replay to {args.out}...")
    html_content = env.render(mode="html")
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Done! You can open '{args.out}' in any web browser to watch the game.")

if __name__ == "__main__":
    main()
