#!/usr/bin/env python3
import os, sys, random, time, multiprocessing
multiprocessing.set_start_method("fork", force=True)
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = {
    "1200-latest-v2-light-v5-safe-terminal": os.path.join(_BASE, "extracted_agents/1200-latest-v2-light-v5-safe-terminal_main.py"),
    "agent-lyonel-1200lb": os.path.join(_BASE, "extracted_agents/agent-lyonel-1200lb_main.py"),
    "light-ver-1200-simple-orbit-intruder": os.path.join(_BASE, "extracted_agents/light-ver-1200-simple-orbit-intruder_main.py"),
    "the-producer-v2": os.path.join(_BASE, "extracted_agents/the-producer-v2_main.py"),
    "apex-hybrid-dynamic": os.path.join(_BASE, "extracted_agents/apex-hybrid-dynamic-ring-control-border_main.py"),
    "best-notebook-agent": os.path.join(_BASE, "extracted_agents/best-orbit-wars-notebook_main.py"),
    "v8-max-1250": os.path.join(_BASE, "extracted_agents/v8-max-1250_main.py"),
    "i-the-orbit": os.path.join(_BASE, "extracted_agents/i-the-orbit_main.py"),
}

def run_match_worker(args):
    seed, agent_paths, player_names = args
    import sys
    import os
    import importlib.util
    import logging
    import gc
    
    logging.disable(logging.INFO)
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    
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
            
            old_path = list(sys.path)
            workspace_root = os.path.dirname(os.path.dirname(abs_path))
            
            if dir_name not in sys.path:
                sys.path.insert(0, dir_name)
            if workspace_root not in sys.path:
                sys.path.insert(0, workspace_root)
                
            module_name = f"mini_worker_{idx}_{os.getpid()}_{id(path)}_{random.randint(0, 1000000)}"
            loaded_module_names.append(module_name)
            
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, "agent"):
                loaded_agents.append(module.agent)
            else:
                return {"success": False, "error": f"No agent function in {path}"}
                
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
            "error": f"Match crash: {str(e)}"
        }
    finally:
        loaded_agents = None
        for m_name in loaded_module_names:
            if m_name in sys.modules:
                del sys.modules[m_name]
        gc.collect()

def run_tournament():
    agent_names = list(AGENTS.keys())
    print("=================================================================")
    print("Starting Orbit Wars Mini-Tournament (2P Round-Robin)")
    for name, path in AGENTS.items():
        print(f"  - {name}: {path}")
    print("=================================================================")

    pairings = []
    for i in range(len(agent_names)):
        for j in range(i + 1, len(agent_names)):
            pairings.append((agent_names[i], agent_names[j]))
            
    seeds = [42 + i for i in range(50)]  # 50 seeds -> 100 matches per pairing
    tasks = []
    for p1, p2 in pairings:
        for seed in seeds:
            tasks.append((seed, [AGENTS[p1], AGENTS[p2]], [p1, p2]))
            tasks.append((seed, [AGENTS[p2], AGENTS[p1]], [p2, p1]))
            
    print(f"Total Matches to run: {len(tasks)}")
    
    results = []
    start_time = time.time()
    with ProcessPoolExecutor(max_workers=14) as executor:
        futures = [executor.submit(run_match_worker, task) for task in tasks]
        for future in as_completed(futures):
            results.append(future.result())
            
    elapsed = time.time() - start_time
    print(f"Tournament finished in {elapsed:.2f} seconds.")
    
    wins = defaultdict(float)
    played = defaultdict(int)
    h2h = defaultdict(lambda: defaultdict(float))
    
    for res in results:
        if not res["success"]:
            print(f"Warning match failed: {res.get('error')}")
            continue
        p_res = res["results"]
        p1_name, p2_name = p_res[0]["name"], p_res[1]["name"]
        p1_rew, p2_rew = p_res[0]["reward"], p_res[1]["reward"]
        
        played[p1_name] += 1
        played[p2_name] += 1
        
        if p1_rew > p2_rew:
            wins[p1_name] += 1.0
            h2h[p1_name][p2_name] += 1.0
        elif p2_rew > p1_rew:
            wins[p2_name] += 1.0
            h2h[p2_name][p1_name] += 1.0
        else:
            wins[p1_name] += 0.5
            wins[p2_name] += 0.5
            h2h[p1_name][p2_name] += 0.5
            h2h[p2_name][p1_name] += 0.5

    leaderboard = []
    for name in agent_names:
        w = wins[name]
        p = played[name]
        rate = (w / p * 100) if p > 0 else 0.0
        leaderboard.append((name, w, p, rate))
    leaderboard.sort(key=lambda x: x[3], reverse=True)
    
    print("\n================== 2P Leaderboard ==================")
    print(f"{'Rank':<5}{'Agent Name':<40}{'Wins':<10}{'Played':<10}{'Win Rate':<10}")
    for rank, (name, w, p, rate) in enumerate(leaderboard, 1):
        print(f"{rank:<5}{name:<40}{w:<10.1f}{p:<10}{rate:<10.2f}%")
    print("====================================================")

if __name__ == "__main__":
    run_tournament()
