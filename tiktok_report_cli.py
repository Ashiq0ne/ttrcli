import requests
import random
import time
import json
import os
import csv
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
from requests.exceptions import RequestException
from fake_useragent import UserAgent

# Disable SSL Warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

delay = config.get("delay_seconds", 2)
retry_limit = config.get("retry_limit", 3)
proxy_mode = config.get("proxy_mode", "none")
proxy_file = config.get("proxy_file", "working_proxies.txt")
log_success = config.get("log_success", "logs/success_log.txt")
log_fail = config.get("log_fail", "logs/error_log.txt")
use_bulk_mode = config.get("use_bulk_mode", False)
target_csv = config.get("target_csv", "targets.csv")

# User-Agent with fallback
try:
    ua = UserAgent()
except:
    class FakeUA:
        @property
        def random(self):
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/90.0.4430.93 Safari/537.36"
    ua = FakeUA()

# Ensure logs folder exists
for log_path in [log_success, log_fail]:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

# Load proxies
def load_proxies():
    proxies = []
    if proxy_mode == "file" and os.path.exists(proxy_file):
        with open(proxy_file, "r") as f:
            proxies = [line.strip() for line in f if ':' in line]
    elif proxy_mode == "auto":
        print("[+] Fetching proxies from GitHub list ...")
        try:
            url = "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"
            raw = requests.get(url, timeout=10).text
            proxies = [line.strip() for line in raw.splitlines() if ':' in line]
            with open(proxy_file, "w") as f:
                for p in proxies:
                    f.write(p + "\n")
        except Exception as e:
            print(f"[ERROR] Proxy fetch failed: {e}")
    return proxies

# Validate proxy
def test_proxy(proxy):
    try:
        r = requests.get("http://www.google.com", proxies={
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }, timeout=5)
        return r.status_code == 200
    except:
        return False

# Load working proxies
working_proxies = []
if proxy_mode != "none":
    print("[*] Validating proxies...")
    all_proxies = load_proxies()
    for p in all_proxies:
        if test_proxy(p):
            working_proxies.append(p)
    print(f"[✓] {len(working_proxies)} working proxies loaded.\n")

# Load targets
def load_targets():
    targets = []
    if use_bulk_mode and os.path.exists(target_csv):
        with open(target_csv, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0]:
                    uid = row[0].strip()
                    if not uid.startswith("@"):
                        uid = "@" + uid
                    targets.append(uid)
    else:
        uid = input("Enter TikTok User ID to report (with or without @): ").strip()
        if not uid.startswith("@"):
            uid = "@" + uid
        targets.append(uid)
    return targets

# Simulated report submission
def report_user(username, proxy=None):
    headers = {
        "User-Agent": ua.random,
        "Content-Type": "application/json"
    }
    data = {
        "user_id": username,
        "reason": "abuse"
    }
    proxies = {}
    if proxy:
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }

    try:
        r = requests.post("https://www.tiktok.com/api/report/user/submit/?aid=1988",  # ← Replace with real or simulated endpoint
                          headers=headers,
                          json=data,
                          proxies=proxies,
                          timeout=10,
                          verify=False)
        if r.status_code in [200, 204]:
            return True
        elif r.status_code == 429:
            print("[!] Rate Limited. Increasing delay might help.")
    except RequestException as e:
        print(f"[EXCEPTION] {e}")
    return False

# Save logs
def save_log(file_path, line):
    with open(file_path, "a") as f:
        f.write(line + "\n")

# Main loop
def run_report_loop(targets):
    success = 0
    fail = 0

    for username in targets:
        retries = 0
        done = False
        while not done and retries < retry_limit:
            proxy = None
            if proxy_mode != "none" and working_proxies:
                proxy = random.choice(working_proxies)
            print(f"[>] Reporting {username} via {proxy or 'No Proxy'} ...")
            if report_user(username, proxy):
                print(f"[✓] Report sent for {username}")
                save_log(log_success, f"{username} | {proxy or 'No Proxy'} | {datetime.now()}")
                success += 1
                done = True
            else:
                print(f"[✗] Failed for {username}")
                save_log(log_fail, f"{username} | {proxy or 'No Proxy'} | {datetime.now()}")
                fail += 1
                retries += 1
            time.sleep(delay)

    print("\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Failed: {fail}")

# Entry point
if __name__ == "__main__":
    try:
        targets = load_targets()
        while True:
            run_report_loop(targets)
            print(f"\n[⏳] Sleeping for {delay * 5} seconds before next loop...\n")
            time.sleep(delay * 5)  # Change multiplier as needed
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
