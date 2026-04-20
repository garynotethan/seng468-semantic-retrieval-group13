#!/usr/bin/env python3
import subprocess
import os
import time
import sys
import csv
import threading
from datetime import datetime

# --- Configuration ---
HOST = "http://localhost:8080"
TEST_DURATION = "1m"
SPAWN_RATE = 2
RESULTS_DIR = "test_results"

# Experiments to run
EXPERIMENTS = [
    {"name": "baseline", "users": 10, "workers": 2, "desc": "Baseline (10 Users, 2 Workers)"},
    {"name": "sustained", "users": 50, "workers": 2, "desc": "Sustained Load (50 Users, 2 Workers)"},
    {"name": "sweep_1w", "users": 10, "workers": 1, "desc": "Worker Sweep (10 Users, 1 Worker)"},
    {"name": "sweep_4w", "users": 10, "workers": 4, "desc": "Worker Sweep (10 Users, 4 Worker)"},
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

def main():
    if not os.path.exists("tests/locustfile.py"):
        print("Error: tests/locustfile.py not found. Run from project root.")
        sys.exit(1)

    print("🚀 Starting Full Performance Benchmark Suite")
    summary_results = []

    for exp in EXPERIMENTS:
        start_services(exp["workers"])
        # 1. Warmup
        run_locust(exp["name"], exp["users"], SPAWN_RATE, TEST_DURATION, is_warmup=True)
        # 2. Actual Benchmark
        csv_path = run_locust(exp["name"], exp["users"], SPAWN_RATE, TEST_DURATION, is_warmup=False)
        stats = extract_summary(csv_path)
        if stats:
            stats["Experiment"] = exp["desc"]
            stats["Users"] = exp["users"]
            stats["Workers"] = exp["workers"]
            summary_results.append(stats)

    # Output Summary Table
    print("\n" + "="*80)
    print("📊 BENCHMARK SUMMARY")
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
    
    print("\n✅ Benchmark suite completed!")
    print(f"📄 Summary saved to: {summary_path}")

if __name__ == "__main__":
    main()
