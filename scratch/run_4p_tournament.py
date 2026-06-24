#!/usr/bin/env python3
import os, sys, random, time, itertools, multiprocessing
multiprocessing.set_start_method("fork", force=True)
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = {
    "1200-latest":   os.path.join(_BASE, "extracted_agents/1200-latest-v2-light-v5-safe-terminal_main.py"),
    "lyonel-1200lb": os.path.join(_BASE, "extracted_agents/agent-lyonel-1200lb_main.py"),
    "apex-hybrid":   os.path.join(_BASE, "extracted_agents/apex-hybrid-dynamic-ring-control-border_main.py"),
    "producer-v2":   os.path.join(_BASE, "extracted_agents/the-producer-v2_main.py"),
    "light-intruder":os.path.join(_BASE, "extracted_agents/light-ver-1200-simple-orbit-intruder_main.py"),
    "best-notebook": os.path.join(_BASE, "extracted_agents/best-orbit-wars-notebook_main.py"),
    "v8-max-1250":   os.path.join(_BASE, "extracted_agents/v8-max-1250_main.py"),
    "i-the-orbit":   os.path.join(_BASE, "extracted_agents/i-the-orbit_main.py"),
}

def run_match_worker(args):
    seed, agent_paths, player_names = args
    import importlib.util, logging, gc
    logging.disable(logging.INFO)
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    try:
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except Exception:
        pass
    loaded_module_names = []
    loaded_agents = []
    try:
        for idx, path in enumerate(agent_paths):
            abs_path = os.path.abspath(path)
            old = list(sys.path)
            sys.path.insert(0, os.path.dirname(abs_path))
            sys.path.insert(0, os.path.dirname(os.path.dirname(abs_path)))
            mname = f"t4p_{idx}_{os.getpid()}_{random.randint(0,999999)}"
            loaded_module_names.append(mname)
            spec = importlib.util.spec_from_file_location(mname, abs_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mname] = mod
            spec.loader.exec_module(mod)
            loaded_agents.append(mod.agent)
            sys.path = old
        from kaggle_environments import make
        env = make("orbit_wars", configuration={"seed": seed}, debug=False)
        env.run(loaded_agents)
        final = env.steps[-1]
        rewards = [final[i].reward for i in range(4)]
        return {"success": True, "names": player_names, "rewards": rewards}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        for m in loaded_module_names:
            sys.modules.pop(m, None)
        gc.collect()

def run_tournament():
    agent_names = list(AGENTS.keys())
    print("=================================================================")
    print("Starting Orbit Wars 4P Tournament")
    print("=================================================================")
    combos = list(itertools.combinations(agent_names, 4))
    seeds = list(range(1000, 1030))
    tasks = []
    for combo in combos:
        for seed in seeds:
            order = list(combo)
            random.shuffle(order)
            tasks.append((seed, [AGENTS[n] for n in order], order))
    print(f"총 게임 수: {len(tasks)}")
    wins = defaultdict(float)
    played = defaultdict(int)
    points = defaultdict(float)
    start = time.time()
    with ProcessPoolExecutor(max_workers=14, max_tasks_per_child=1) as executor:
        futures = [executor.submit(run_match_worker, t) for t in tasks]
        done = 0
        for future in as_completed(futures):
            res = future.result()
            done += 1
            if not res["success"]:
                continue
            names = res["names"]
            rewards = res["rewards"]
            sorted_r = sorted(set(rewards), reverse=True)
            for i, name in enumerate(names):
                played[name] += 1
                rank = sorted_r.index(rewards[i])
                rank_pts = [3, 2, 1, 0][rank]
                points[name] += rank_pts
                if rank == 0 and rewards.count(rewards[i]) == 1:
                    wins[name] += 1.0
                elif rank == 0:
                    wins[name] += 0.5
            if done % 20 == 0:
                print(f"  진행 중: {done}/{len(tasks)}")
    elapsed = time.time() - start
    print(f"\n완료: {elapsed:.1f}초\n")
    leaderboard = []
    for name in agent_names:
        p = played[name]
        w = wins[name]
        pt = points[name]
        avg_pt = pt / p if p > 0 else 0
        win_rate = w / p * 100 if p > 0 else 0
        leaderboard.append((name, w, p, win_rate, avg_pt))
    leaderboard.sort(key=lambda x: x[4], reverse=True)
    print(f"{'순위':<5}{'봇 이름':<20}{'승':<8}{'게임':<8}{'승률':<10}{'평균포인트'}")
    print("-" * 60)
    for rank, (name, w, p, wr, apt) in enumerate(leaderboard, 1):
        print(f"{rank:<5}{name:<20}{w:<8.1f}{p:<8}{wr:<10.1f}%{apt:.2f}")

if __name__ == "__main__":
    run_tournament()
