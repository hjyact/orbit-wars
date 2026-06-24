#!/usr/bin/env python3
import os
import sys
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict

# Map of agent names to their file paths (10 unique agents)
AGENTS = {
    "1200-latest-v2-light-v5-safe-terminal": "extracted_agents/1200-latest-v2-light-v5-safe-terminal_main.py",
    "agent-lyonel-1200lb": "extracted_agents/agent-lyonel-1200lb_main.py",
    "light-ver-1200-simple-orbit-intruder": "extracted_agents/light-ver-1200-simple-orbit-intruder_main.py",
    "orbit-wars-exp50": "extracted_agents/orbit-wars-exp50_main.py",
    "orbit-wars-i-m-stronger": "extracted_agents/orbit-wars-i-m-stronger_main.py",
    "the-producer-v2": "extracted_agents/the-producer-v2_main.py",
    "orbit-wars": "extracted_agents/orbit-wars_main.py",
    "v2-gru": "extracted_agents/v2-gru_main.py",
    "buddy-other-orbit-wars-v4": "extracted_agents/buddy-other-orbit-wars-v4/main.py",
    "agent_combined_elite": "extracted_agents/agent_combined_elite_main.py",
    "optimized-agent": "main.py"
}

def run_match_worker(args):
    """
    Worker function to run a single match.
    """
    seed, agent_paths, player_names = args
    import sys
    import os
    import importlib.util
    import logging
    import gc
    
    # Silence logging
    logging.disable(logging.INFO)
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    
    # Force single-threaded PyTorch
    try:
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except Exception:
        pass
        
    from kaggle_environments import make

    loaded_agents = []
    loaded_module_names = []
    
    try:
        for idx, path in enumerate(agent_paths):
            abs_path = os.path.abspath(path)
            dir_name = os.path.dirname(abs_path)
            
            # Insert agent folder AND the root workspace to sys.path so orbit_lite can be found
            old_path = list(sys.path)
            workspace_root = os.path.dirname(os.path.dirname(abs_path)) # Parent of extracted_agents/
            
            if dir_name not in sys.path:
                sys.path.insert(0, dir_name)
            if workspace_root not in sys.path:
                sys.path.insert(0, workspace_root)
                
            module_name = f"worker_agent_{idx}_{os.getpid()}_{id(path)}"
            loaded_module_names.append(module_name)
            try:
                spec = importlib.util.spec_from_file_location(module_name, abs_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                if hasattr(module, "agent"):
                    loaded_agents.append(module.agent)
                else:
                    return {
                        "success": False,
                        "error": f"No agent function in {path}",
                        "player_names": player_names
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to load {path}: {str(e)}",
                    "player_names": player_names
                }
            finally:
                sys.path = old_path

        env = make("orbit_wars", configuration={"seed": seed}, debug=False)
        env.run(loaded_agents)
        
        final_step = env.steps[-1]
        results = []
        for idx, s in enumerate(final_step):
            results.append({
                "name": player_names[idx],
                "reward": s.reward,
                "status": s.status
            })
        return {
            "success": True,
            "results": results,
            "seed": seed
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Match crash: {str(e)}",
            "player_names": player_names
        }
    finally:
        # Clean up references to agents
        loaded_agents = None
        # Clean up modules from sys.modules
        for m_name in loaded_module_names:
            if m_name in sys.modules:
                del sys.modules[m_name]
        # Clean up PyTorch cache if CPU/CUDA tensors were created
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()

def run_tournament():
    agent_names = list(AGENTS.keys())
    
    print("=================================================================")
    print("Starting Orbit Wars Local Downloads Tournament (2P and 4P)")
    print(f"Candidates ({len(agent_names)} unique files):")
    for name, path in AGENTS.items():
        print(f"  - {name} ({path})")
    print("=================================================================")

    max_workers = 4
    
    # -----------------------------------------------------------------
    # Part 1: 2P (1v1) Round-Robin Tournament
    # -----------------------------------------------------------------
    print("\n[1/2] Generating 2P (1v1) Match List...")
    pairings = []
    for i in range(len(agent_names)):
        for j in range(i + 1, len(agent_names)):
            pairings.append((agent_names[i], agent_names[j]))
            
    # Run 20 matches per pair (10 seeds, swapping P1 and P2)
    seeds_2p = [100 + i for i in range(10)]
    tasks_2p = []
    
    for p1, p2 in pairings:
        for seed in seeds_2p:
            tasks_2p.append((seed, [AGENTS[p1], AGENTS[p2]], [p1, p2]))
            tasks_2p.append((seed, [AGENTS[p2], AGENTS[p1]], [p2, p1]))
            
    print(f"Total 2P Matches to run: {len(tasks_2p)}")
    
    results_2p = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_match_worker, task) for task in tasks_2p]
        completed = 0
        for future in as_completed(futures):
            res = future.result()
            results_2p.append(res)
            completed += 1
            if completed % 20 == 0 or completed == len(tasks_2p):
                print(f"  Progress: {completed}/{len(tasks_2p)} matches completed...")
                 
    elapsed_2p = time.time() - start_time
    print(f"2P Tournament Finished in {elapsed_2p:.2f} seconds.")
    
    wins_2p = defaultdict(int)
    played_2p = defaultdict(int)
    h2h_wins = defaultdict(lambda: defaultdict(int))
    h2h_played = defaultdict(lambda: defaultdict(int))
    
    for res in results_2p:
        if not res["success"]:
            print(f"Warning: 2P Match failed: {res.get('error')}")
            continue
            
        p_res = res["results"]
        p1_name, p2_name = p_res[0]["name"], p_res[1]["name"]
        p1_rew, p2_rew = p_res[0]["reward"], p_res[1]["reward"]
        
        played_2p[p1_name] += 1
        played_2p[p2_name] += 1
        h2h_played[p1_name][p2_name] += 1
        h2h_played[p2_name][p1_name] += 1
        
        if p1_rew > p2_rew:
            wins_2p[p1_name] += 1
            h2h_wins[p1_name][p2_name] += 1
        elif p2_rew > p1_rew:
            wins_2p[p2_name] += 1
            h2h_wins[p2_name][p1_name] += 1
        else:
            wins_2p[p1_name] += 0.5
            wins_2p[p2_name] += 0.5
            h2h_wins[p1_name][p2_name] += 0.5
            h2h_wins[p2_name][p1_name] += 0.5

    # -----------------------------------------------------------------
    # Part 2: 4P (FFA) Tournament
    # -----------------------------------------------------------------
    print("\n[2/2] Generating 4P (FFA) Match List...")
    num_ffa_matches = 150
    seeds_4p = [1000 + i for i in range(num_ffa_matches)]
    tasks_4p = []
    
    for i in range(num_ffa_matches):
        match_agents = random.sample(agent_names, 4)
        tasks_4p.append((seeds_4p[i], [AGENTS[name] for name in match_agents], match_agents))
        
    print(f"Total 4P Matches to run: {len(tasks_4p)}")
    
    results_4p = []
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_match_worker, task) for task in tasks_4p]
        completed = 0
        for future in as_completed(futures):
            res = future.result()
            results_4p.append(res)
            completed += 1
            if completed % 20 == 0 or completed == len(tasks_4p):
                print(f"  Progress: {completed}/{len(tasks_4p)} matches completed...")
                
    elapsed_4p = time.time() - start_time
    print(f"4P Tournament Finished in {elapsed_4p:.2f} seconds.")
    
    plays_4p = defaultdict(int)
    wins_4p = defaultdict(int)
    total_rewards_4p = defaultdict(float)
    
    for res in results_4p:
        if not res["success"]:
            print(f"Warning: 4P Match failed: {res.get('error')}")
            continue
            
        p_res = res["results"]
        for p in p_res:
            name = p["name"]
            reward = p["reward"]
            
            plays_4p[name] += 1
            total_rewards_4p[name] += reward
            if reward == 1.0:
                wins_4p[name] += 1

    # -----------------------------------------------------------------
    # Save Results
    # -----------------------------------------------------------------
    leaderboard_2p = []
    for name in agent_names:
        w = wins_2p[name]
        p = played_2p[name]
        rate = (w / p * 100) if p > 0 else 0
        leaderboard_2p.append((name, w, p, rate))
    leaderboard_2p.sort(key=lambda x: x[3], reverse=True)
    
    leaderboard_4p = []
    for name in agent_names:
        w = wins_4p[name]
        p = plays_4p[name]
        rate = (w / p * 100) if p > 0 else 0
        avg_reward = (total_rewards_4p[name] / p) if p > 0 else 0
        leaderboard_4p.append((name, w, p, rate, avg_reward))
    leaderboard_4p.sort(key=lambda x: x[3], reverse=True)

    report_path = "downloads_tournament_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Downloads Tournament Results Report\n\n")
        f.write(f"This tournament evaluated the 9 unique agents from the Downloads folder in both **2P (1v1)** and **4P (FFA)** settings. ")
        f.write(f"A total of **{len(tasks_2p)}** 1v1 matches and **{num_ffa_matches}** FFA matches were simulated.\n\n")
        
        f.write("## 2P (1v1) Leaderboard\n")
        f.write("| Rank | Agent Name | Wins | Played | Win Rate |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        for rank, (name, w, p, rate) in enumerate(leaderboard_2p, 1):
            f.write(f"| {rank} | `{name}` | {w:.1f} | {p} | **{rate:.2f}%** |\n")
            
        f.write("\n## 2P Head-to-Head Win Rate Matrix (%)\n")
        h_cols = "| Agent (Row) vs Agent (Col) | " + " | ".join([f"`{n}`" for n in agent_names]) + " |\n"
        h_sep = "| --- | " + " | ".join(["---"] * len(agent_names)) + " |\n"
        f.write(h_cols)
        f.write(h_sep)
        for name_row in agent_names:
            row_str = f"| `{name_row}` | "
            cols = []
            for name_col in agent_names:
                if name_row == name_col:
                    cols.append("-")
                else:
                    played = h2h_played[name_row][name_col]
                    wins = h2h_wins[name_row][name_col]
                    rate = (wins / played * 100) if played > 0 else 0.0
                    cols.append(f"{rate:.1f}%")
            row_str += " | ".join(cols) + " |\n"
            f.write(row_str)
            
        f.write("\n## 4P (FFA) Leaderboard\n")
        f.write("| Rank | Agent Name | Wins | Played | Win Rate (1st Place) | Avg Reward |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for rank, (name, w, p, rate, avg_reward) in enumerate(leaderboard_4p, 1):
            f.write(f"| {rank} | `{name}` | {w} | {p} | **{rate:.2f}%** | {avg_reward:.3f} |\n")
            
        f.write("\n\n### Summary Findings:\n")
        f.write(f"- **Strongest 2P (1v1) Agent**: `{leaderboard_2p[0][0]}` (Win Rate: {leaderboard_2p[0][3]:.2f}%)\n")
        f.write(f"- **Strongest 4P (FFA) Agent**: `{leaderboard_4p[0][0]}` (Win Rate: {leaderboard_4p[0][3]:.2f}%)\n")
        
    print(f"\nWritten markdown report to '{report_path}'.")

if __name__ == "__main__":
    run_tournament()
