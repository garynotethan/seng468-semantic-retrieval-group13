#!/usr/bin/env python3
import subprocess
import os
import argparse
import time
import sys
import platform
import psutil
import threading
from datetime import datetime

class ContainerMonitor(threading.Thread):
    """Background thread to monitor docker container stats."""
    def __init__(self, results_dir, timestamp, interval=2):
        super().__init__()
        self.results_dir = results_dir
        self.timestamp = timestamp
        self.interval = interval
        self.stop_event = threading.Event()
        self.output_file = os.path.join(results_dir, f"container_stats_{timestamp}.txt")

    def run(self):
        with open(self.output_file, "w") as f:
            f.write(f"=== Container Performance Log ({datetime.now()}) ===\n")
            f.write("Interval: {}s\n\n".format(self.interval))
            
            while not self.stop_event.is_set():
                try:
                    # Get stats for all running containers in the current project
                    # We use --no-stream to get a single snapshot
                    result = subprocess.run(
                        ["docker", "stats", "--no-stream", "--format", 
                         "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"],
                        capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        f.write(f"\n--- Snapshot at {datetime.now().strftime('%H:%M:%S')} ---\n")
                        f.write(result.stdout)
                        f.flush()
                except Exception as e:
                    f.write(f"Error capturing stats: {e}\n")
                
                time.sleep(self.interval)

    def stop(self):
        self.stop_event.set()

def get_hardware_info():
    """Captures basic hardware specifications."""
    try:
        info = [
            "=== Hardware Specifications ===",
            f"OS: {platform.system()} {platform.release()}",
            f"Processor: {platform.processor()}",
            f"CPU Count: {psutil.cpu_count(logical=True)} (Logical), {psutil.cpu_count(logical=False)} (Physical)",
            f"RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB",
            ""
        ]
        return "\n".join(info)
    except Exception as e:
        return f"Could not capture hardware info: {e}"

def check_services():
    print("🔍 Checking if services are up...")
    try:
        # Check if the API is responding
        import http.client
        conn = http.client.HTTPConnection("localhost", 8080)
        conn.request("GET", "/documents") # Should return 401 or similar if up
        response = conn.getresponse()
        print("✅ API is reachable on localhost:8080")
        return True
    except Exception:
        print("❌ API is not reachable on localhost:8080")
        return False

def start_services(workers=None):
    print("🏗️ Starting services via docker-compose...")
    env = os.environ.copy()
    if workers:
        env["GUNICORN_WORKERS"] = str(workers)
        print(f"👷 Configuring Gunicorn with {workers} workers")
    
    try:
        subprocess.run(["docker", "compose", "up", "-d", "--build"], env=env, check=True)
        wait_time = 15 if workers and workers > 4 else 10
        print(f"⏳ Waiting for services to stabilize ({wait_time}s)...")
        time.sleep(wait_time)
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to start services.")
        return False

def run_integration_tests():
    print("\n🧪 Running Integration Tests (unittest)...")
    try:
        subprocess.run([sys.executable, "tests/test_api.py"], check=True)
        print("✅ Integration tests passed!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Integration tests failed.")
        return False

def run_load_tests(host, users, spawn_rate, run_time, tags=None):
    print(f"\n🚀 Running Load Tests (Locust) against {host}...")
    results_dir = os.path.join(os.getcwd(), "test_results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(results_dir, f"report_{timestamp}.html")
    csv_prefix = os.path.join(results_dir, f"results_{timestamp}")

    cmd = [
        "locust",
        "-f", "tests/locustfile.py",
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", run_time,
        "--host", host,
        "--csv", csv_prefix,
        "--html", report_file
    ]

    if tags:
        cmd.extend(["--tags", tags])

    print(f"👥 Users: {users}, 📈 Spawn Rate: {spawn_rate}, ⏱️ Duration: {run_time}")
    
    # Save hardware info
    hardware_info = get_hardware_info()
    with open(os.path.join(results_dir, f"hardware_info_{timestamp}.txt"), "w") as f:
        f.write(hardware_info)

    # Start container monitoring
    monitor = ContainerMonitor(results_dir, timestamp)
    monitor.start()

    try:
        subprocess.run(cmd, check=True)
        print("✅ Load tests completed!")
        print(f"📊 Results: {results_dir}")
        print(f"📄 HTML Report: {report_file}")
        return True
    except subprocess.CalledProcessError:
        print("❌ Load tests failed.")
        return False
    finally:
        monitor.stop()
        monitor.join()
        print(f"📄 Container Stats: {monitor.output_file}")
    
    return report_file

def benchmark_workers(host, users, spawn_rate, run_time):
    """Sweeps through different worker counts to find the optimum."""
    worker_counts = [1, 2, 4]
    print(f"\n📈 Starting Worker Benchmark Sweep: {worker_counts}")
    results = []
    
    for count in worker_counts:
        print(f"\n--- Testing with {count} Workers ---")
        if not start_services(workers=count):
            continue
        
        report = run_load_tests(host, users, spawn_rate, run_time)
        results.append((count, report))
        
    print("\n🏁 Worker Benchmark Sweep Completed!")
    for count, report in results:
        print(f" - {count} Workers: {report}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-stop shop for all API testing.")
    parser.add_argument("--host", default="http://localhost:8080", help="Host for load tests")
    parser.add_argument("--no-load", action="store_true", help="Skip load tests")
    parser.add_argument("--no-int", action="store_true", help="Skip integration tests")
    parser.add_argument("--start", action="store_true", help="Force start/restart services")
    parser.add_argument("-u", "--users", type=int, default=10, help="Locust users")
    parser.add_argument("-r", "--spawn-rate", type=int, default=2, help="Locust spawn rate")
    parser.add_argument("-t", "--run-time", default="1m", help="Locust run time")
    parser.add_argument("-w", "--workers", type=int, help="Specify Gunicorn workers for this run")
    parser.add_argument("--benchmark-workers", action="store_true", help="Run a sweep of 1, 2, and 4 workers")

    args = parser.parse_args()

    # 1. Check/Start Services
    if args.benchmark_workers:
        # Benchmark mode handles its own startup
        benchmark_workers(args.host, args.users, args.spawn_rate, args.run_time)
        print("\n🏁 Benchmark suite finished.")
        sys.exit(0)

    if args.start or args.workers or not check_services():
        if not start_services(workers=args.workers):
            sys.exit(1)
        # Re-check after starting
        if not check_services():
            print("❌ Services still not reachable. Exiting.")
            sys.exit(1)

    # 2. Integration Tests
    if not args.no_int:
        run_integration_tests()

    # 3. Load Tests
    if not args.no_load:
        run_load_tests(args.host, args.users, args.spawn_rate, args.run_time)

    print("\n🏁 Automation script finished.")
