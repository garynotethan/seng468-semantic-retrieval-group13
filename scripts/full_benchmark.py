#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import csv
import threading
import argparse
from datetime import datetime

# --- Configuration ---
HOST = "http://localhost:8080"
TEST_DURATION = "1m"
SPAWN_RATE = 2
RESULTS_DIR = "test_results"
API_CONTAINER = "seng468-semantic-retrieval-group13-api-1"
WORKER_CONTAINER = "seng468-semantic-retrieval-group13-worker-1"

# Experiments to run
EXPERIMENTS = [
    {"name": "baseline", "users": 10, "workers": 2, "desc": "Baseline (10 Users, 2 Workers)"},
    {"name": "sustained", "users": 50, "workers": 2, "desc": "Sustained Load (50 Users, 2 Workers)"},
    {"name": "sweep_1w", "users": 10, "workers": 1, "desc": "Worker Sweep (10 Users, 1 Worker)"},
    {"name": "sweep_4w", "users": 10, "workers": 4, "desc": "Worker Sweep (10 Users, 4 Worker)"},
    {"name": "breaking_point", "users": 200, "workers": 2, "desc": "Stress Test (200 Users, 2 Workers)"},
]

def run_command(cmd, env=None):
    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, env=env, check=True)

def start_services(workers):
    print(f"\n--- Restarting services with {workers} Gunicorn workers ---")
    env = os.environ.copy()
    env["GUNICORN_WORKERS"] = str(workers)
    # Force rebuild to ensure env changes are picked up if they affect the build
    run_command(["docker", "compose", "up", "-d", "--build"], env=env)
    print("Waiting 15s for services to stabilize...")
    time.sleep(15)

def run_locust(name, users, spawn_rate, duration, is_warmup=False):
    stage = "WARMUP" if is_warmup else "BENCHMARK"
    print(f"\n--- Running {stage}: {name} ({users} users) ---")
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_prefix = os.path.join(RESULTS_DIR, f"{name}_{timestamp}")
    report_file = os.path.join(RESULTS_DIR, f"{name}_{timestamp}.html")
    
    # In warmup mode, we don't care about saving the CSV results long-term
    # but we need to pass a prefix
    actual_prefix = f"{csv_prefix}_warmup" if is_warmup else csv_prefix

    cmd = [
        "locust",
        "-f", "tests/locustfile.py",
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", "30s" if is_warmup else duration,
        "--host", HOST,
        "--csv", actual_prefix,
        "--html", report_file
    ]
    
    run_command(cmd)
    return f"{actual_prefix}_stats.csv"

def record_profile(container, name, duration):
    """Starts a py-spy recording in the background."""
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
    
    output_file = os.path.join(RESULTS_DIR, f"profile_{container}_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg")
    print(f"--- Profiling {container} for {duration} -> {output_file} ---")
    
    # We find the PID of the main gunicorn/python process in the container
    # pid 1 is usually the entrypoint, but we want to be sure.
    cmd = [
        "docker", "exec", "-d", container,
        "py-spy", "record", "-o", f"/tmp/profile.svg", "--duration", duration, "--pid", "1"
    ]
    try:
        subprocess.run(cmd, check=False)
        # We need a follow up to copy the file out after duration
        return output_file
    except Exception as e:
        print(f"Failed to start profiling: {e}")
        return None

def collect_profile(container, host_path):
    """Copies the profile SVG from the container to the host."""
    time.sleep(2) # brief buffer
    cmd = ["docker", "cp", f"{container}:/tmp/profile.svg", host_path]
    try:
        subprocess.run(cmd, check=False)
    except Exception as e:
        print(f"Failed to collect profile: {e}")

def extract_summary(csv_path):
    """Extracts the 'Aggregated' row from Locust stats CSV."""
    try:
        with open(csv_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Name") == "Aggregated":
                    return {
                        "RPS": row.get("Requests/s"),
                        "Avg": row.get("Average Response Time"),
                        "P95": row.get("95%"),
                        "Max": row.get("Max Response Time"),
                        "Failures": row.get("Failure Count")
                    }
    except Exception as e:
        print(f"Error parsing {csv_path}: {e}")
    return None

def run_dynamic_stress_test(workers, args):
    """Gradually increases users until the system hits a breaking point."""
    print("\n--- 🕵️ starting Dynamic breaking point discovery ---")
    start_services(workers)
    
    current_users = 50
    increment = 50
    stable_results = []
    breaking_point = None
    
    while True:
        name = f"stress_{current_users}"
        print(f"\n--- Testing with {current_users} users ---")
        
        # Warmup
        run_locust(name, current_users, SPAWN_RATE, TEST_DURATION, is_warmup=True)
        
        # Benchmark
        # (Profiling omitted in dynamic test to keep it fast, but could be added)
        csv_path = run_locust(name, current_users, SPAWN_RATE, TEST_DURATION, is_warmup=False)
        stats = extract_summary(csv_path)
        
        if not stats:
            print("Failed to get stats. Stopping.")
            breaking_point = current_users
            break
            
        requests = float(stats["RPS"]) * 60 # approx total requests
        failures = int(stats["Failures"])
        failure_rate = (failures / requests) if requests > 0 else 0
        avg_latency = float(stats["Avg"])
        
        stats["Users"] = current_users
        stats["Workers"] = workers
        stats["Experiment"] = f"Stress {current_users}"
        
        print(f"Results: {failure_rate:.2%} failures, {avg_latency:.1f}ms avg latency")
        
        # Breaking Conditions
        if failure_rate > 0.01:
            print(f"BREAK: Failure rate {failure_rate:.2%} exceeded 1%")
            breaking_point = current_users
            break
        if avg_latency > 5000:
            print(f"BREAK: Avg latency {avg_latency:.1f}ms exceeded 5s")
            breaking_point = current_users
            break
            
        stable_results.append(stats)
        current_users += increment
        
    print("\n" + "="*40)
    print(f"DYNAMIC TEST COMPLETE")
    print(f"Stable Capacity: {stable_results[-1]['Users'] if stable_results else 0} users")
    print(f"Breaking Point : {breaking_point} users")
    print("="*40)
    return stable_results

def main():
    parser = argparse.ArgumentParser(description="Full Performance Benchmark Suite")
    parser.add_argument("-n", "--name", help="Specific experiment name to run")
    parser.add_argument("-p", "--profile", action="store_true", help="Enable py-spy profiling (requires py-spy in images)")
    parser.add_argument("-a", "--auto-break", action="store_true", help="Run dynamic breaking point test")
    args = parser.parse_args()

    if not os.path.exists("tests/locustfile.py"):
        print("Error: tests/locustfile.py not found. Run from project root.")
        sys.exit(1)

    experiments_to_run = EXPERIMENTS
    if args.name:
        experiments_to_run = [e for e in EXPERIMENTS if e["name"] == args.name]
        if not experiments_to_run:
            print(f"Error: Experiment '{args.name}' not found.")
            print(f"Available experiments: {', '.join([e['name'] for e in EXPERIMENTS])}")
            sys.exit(1)

    print("🚀 Starting Full Performance Benchmark Suite")
    summary_results = []

    if args.auto_break:
        # Use workers from baseline or default to 2
        workers = next((e["workers"] for e in EXPERIMENTS if e["name"] == "baseline"), 2)
        summary_results = run_dynamic_stress_test(workers, args)
    else:
        for exp in experiments_to_run:
            start_services(exp["workers"])
            # 1. Warmup
            run_locust(exp["name"], exp["users"], SPAWN_RATE, TEST_DURATION, is_warmup=True)
            
            # 2. Actual Benchmark
            profile_tasks = []
            if args.profile:
                # Start profiling in background
                d_sec = 60 # Default 1m in seconds
                if TEST_DURATION.endswith('m'):
                    d_sec = int(TEST_DURATION[:-1]) * 60
                elif TEST_DURATION.endswith('s'):
                    d_sec = int(TEST_DURATION[:-1])
                
                p1 = record_profile(API_CONTAINER, exp["name"], str(d_sec))
                p2 = record_profile(WORKER_CONTAINER, exp["name"], str(d_sec))
                if p1: profile_tasks.append((API_CONTAINER, p1))
                if p2: profile_tasks.append((WORKER_CONTAINER, p2))

            csv_path = run_locust(exp["name"], exp["users"], SPAWN_RATE, TEST_DURATION, is_warmup=False)
            
            if args.profile:
                print("--- Collecting profiling results ---")
                for container, path in profile_tasks:
                    collect_profile(container, path)

            stats = extract_summary(csv_path)
            if stats:
                stats["Experiment"] = exp["desc"]
                stats["Users"] = exp["users"]
                stats["Workers"] = exp["workers"]
                summary_results.append(stats)

    # Output Summary Table
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)
    print(f"{'Experiment':<35} | {'RPS':>6} | {'Avg':>8} | {'P95':>8} | {'Max':>8} | {'Fail':>5}")
    print("-" * 80)
    
    md_table = "| Experiment | Users | Workers | RPS | Avg | P95 | Max | Failures |\n"
    md_table += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"

    for r in summary_results:
        print(f"{r['Experiment']:<35} | {float(r['RPS']):>6.2f} | {float(r['Avg']):>8.1f} | {float(r['P95']):>8.0f} | {float(r['Max']):>8.0f} | {r['Failures']:>5}")
        md_table += f"| {r['Experiment']} | {r['Users']} | {r['Workers']} | {float(r['RPS']):.2f} | {float(r['Avg']):.1f} | {r['P95']} | {r['Max']} | {r['Failures']} |\n"

    # Save summary to a file
    summary_path = os.path.join(RESULTS_DIR, f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(summary_path, "w") as f:
        f.write("# benchmark Summary Results\n\n")
        f.write(md_table)
    
    print("\nBenchmark suite completed!")
    print(f"Summary saved to: {summary_path}")

if __name__ == "__main__":
    main()
