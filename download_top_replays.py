import os
import sys
import csv
import json
import time
import subprocess
import re
from pathlib import Path

# Competition Name
COMPETITION = "orbit-wars"
OUTPUT_DIR = Path("/home/hjyact/GitHub/Orbit_Wars/top_replays")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd_list):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd_list)}: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def clean_csv_output(stdout, expected_header_field):
    if not stdout:
        return []
    lines = stdout.splitlines()
    csv_start_idx = -1
    for idx, line in enumerate(lines):
        if expected_header_field in line and "," in line:
            csv_start_idx = idx
            break
    if csv_start_idx == -1:
        # Fallback to filtering out known non-csv messages
        clean_lines = []
        for line in lines:
            if any(line.startswith(w) for w in ["Warning:", "Either", "Next Page Token", "Use", "Downloading", "Replay downloaded"]):
                continue
            clean_lines.append(line)
        return clean_lines
    return lines[csv_start_idx:]

def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def get_top_teams(limit=5):
    print("Fetching leaderboard...")
    stdout = run_cmd(["kaggle", "competitions", "leaderboard", COMPETITION, "--show", "--csv", "--page-size", "20"])
    lines = clean_csv_output(stdout, "teamId")
    if not lines:
        return []
    
    teams = []
    reader = csv.DictReader(lines)
    for row in reader:
        teams.append({
            "teamId": row["teamId"],
            "teamName": row["teamName"],
            "score": float(row["score"])
        })
        if len(teams) >= limit:
            break
    return teams

def get_team_submissions(team_id):
    print(f"Fetching submissions for team {team_id}...")
    stdout = run_cmd(["kaggle", "competitions", "team-submissions", team_id, "--csv"])
    lines = clean_csv_output(stdout, "dateSubmitted")
    if not lines:
        return []
    
    subs = []
    reader = csv.DictReader(lines)
    for row in reader:
        subs.append({
            "id": row["id"],
            "dateSubmitted": row["dateSubmitted"],
            "publicScore": float(row["publicScore"]) if row.get("publicScore") else 0.0
        })
    return subs

def get_submission_episodes(sub_id):
    print(f"Fetching episodes for submission {sub_id}...")
    stdout = run_cmd(["kaggle", "competitions", "episodes", sub_id, "--csv"])
    lines = clean_csv_output(stdout, "createTime")
    if not lines:
        return []
    
    episodes = []
    reader = csv.DictReader(lines)
    for row in reader:
        if row.get("state") == "EpisodeState.COMPLETED":
            episodes.append(row["id"])
    return episodes

def check_if_team_won(replay_path, team_name):
    try:
        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        info = data.get("info", {})
        team_names = info.get("TeamNames", [])
        if not team_names:
            agents = info.get("Agents", [])
            team_names = [a.get("Name") for a in agents if a.get("Name")]
            
        if not team_names:
            print(f"Warning: No team names found in {replay_path.name}")
            return False, "unknown"
        
        steps = data.get("steps", [])
        if not steps:
            return False, "no_steps"
            
        last_step = steps[-1]
        if not isinstance(last_step, list):
            return False, "invalid_steps"
            
        target_idx = -1
        for idx, name in enumerate(team_names):
            if name == team_name:
                target_idx = idx
                break
        if target_idx == -1:
            for idx, name in enumerate(team_names):
                if name.lower() == team_name.lower():
                    target_idx = idx
                    break
                    
        if target_idx == -1:
            print(f"Warning: Target team '{team_name}' not found in team names: {team_names}")
            return False, "team_not_found"
            
        rewards = [agent.get("reward") for agent in last_step if isinstance(agent, dict)]
        rewards = [r if r is not None else -9999.0 for r in rewards]
        if not rewards or len(rewards) <= target_idx:
            return False, "invalid_rewards"
            
        target_reward = rewards[target_idx]
        max_reward = max(rewards)
        
        is_win = (target_reward == max_reward) and (target_reward > min(rewards))
        
        print(f"Episode {replay_path.name.split('-')[1]} - Teams: {team_names} - Rewards: {rewards} - Target: {team_name} (idx {target_idx}, reward {target_reward}) - Won: {is_win}")
        return is_win, "success"
    except Exception as e:
        print(f"Error parsing replay {replay_path.name}: {e}")
        return False, "parse_error"

def main():
    print(f"Downloading top replays for {COMPETITION}...")
    teams = get_top_teams(limit=10)
    print(f"Found top teams: {[t['teamName'] for t in teams]}")
    
    total_downloaded = 0
    total_wins_kept = 0
    
    for team in teams:
        team_id = team["teamId"]
        team_name = team["teamName"]
        clean_team = clean_filename(team_name)
        
        print(f"\n==================================================")
        print(f"Processing Team: {team_name} (ID: {team_id})")
        print(f"==================================================")
        
        subs = get_team_submissions(team_id)
        subs = sorted(subs, key=lambda x: x["publicScore"], reverse=True)
        selected_subs = subs[:2]
        print(f"Selected submissions: {[s['id'] for s in selected_subs]}")
        
        downloaded_episodes = set()
        
        for sub in selected_subs:
            sub_id = sub["id"]
            episodes = get_submission_episodes(sub_id)
            print(f"Found {len(episodes)} completed episodes for submission {sub_id}")
            
            for ep_id in episodes[:15]:
                if ep_id in downloaded_episodes:
                    continue
                downloaded_episodes.add(ep_id)
                
                dest_win_path = OUTPUT_DIR / f"episode_{ep_id}_win_{clean_team}.json"
                
                if dest_win_path.exists():
                    print(f"Episode {ep_id} already downloaded and verified as win for {team_name}")
                    total_wins_kept += 1
                    continue
                
                print(f"Downloading replay for episode {ep_id}...")
                temp_filename = f"episode-{ep_id}-replay.json"
                temp_path = OUTPUT_DIR / temp_filename
                
                if temp_path.exists():
                    temp_path.unlink()
                
                run_cmd(["kaggle", "competitions", "replay", ep_id, "-p", str(OUTPUT_DIR)])
                
                if not temp_path.exists():
                    print(f"Failed to download episode {ep_id}")
                    continue
                
                total_downloaded += 1
                
                is_win, status = check_if_team_won(temp_path, team_name)
                
                if is_win:
                    temp_path.rename(dest_win_path)
                    print(f"Saved winning replay to {dest_win_path.name}")
                    total_wins_kept += 1
                else:
                    temp_path.unlink()
                    print(f"Discarded non-winning/invalid episode {ep_id}")
                
                time.sleep(1.0)
                
    print(f"\n==================================================")
    print(f"Completed! Total downloaded: {total_downloaded}, Total winning replays kept: {total_wins_kept}")
    print(f"==================================================")

if __name__ == "__main__":
    main()
