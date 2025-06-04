import requests, threading, random, time, json, os, csv
from queue import Queue
from datetime import datetime
from requests.exceptions import RequestException
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# === Terminal Config ===
print("\n🔧 Loading configuration from terminal...")

THREADS = int(input("Number of threads (default 10): ") or 10)
RETRY_LIMIT = int(input("Retry limit (default 3): ") or 3)
DELAY = int(input("Delay (seconds): ") or 3)
TIMEOUT = int(input("Timeout (seconds): ") or 10)
USE_BULK = input("Use bulk mode? (y/n): ").strip().lower() == 'y'
CSV_FILE = input("CSV filename (default: targets.csv): ") or "targets.csv"

print("\n🎯 Select reason for reporting:")
reason_map = {
    "1": "nudity",
    "2": "violence",
    "3": "harassment",
    "4": "spam",
    "5": "misinformation",
    "6": "minor_safety",
    "7": "illegal_activities"
}
for key, value in reason_map.items():
    print(f"{key}. {value.replace('_', ' ').title()}")
reason = reason_map.get(input("Enter number (1–7): ").strip(), "nudity")

# === Constants ===
PROXY_FILE = "working_proxies.txt"
USER_AGENT_FILE = "user_agents.txt"
LOG_FILE = "report_log.txt"
SUCCESS_LOG = "logs/success_log.txt"
ERROR_LOG = "logs/error_log.txt"
os.makedirs("logs", exist_ok=True)

report_count = {}  # Track reports per user

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def save_log(file, msg):
    with open(file, "a") as f:
        f.write(f"{msg}\n")

def load_proxies():
    with open(PROXY_FILE) as f:
        return [line.strip() for line in f if line.strip()]

def load_user_agents():
    if os.path.exists(USER_AGENT_FILE):
        with open(USER_AGENT_FILE) as f:
            return [ua.strip() for ua in f if ua.strip()]
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    ]

def get_random_proxy(proxies):
    proxy = random.choice(proxies)
    return {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }, proxy

def get_random_user_agent(user_agents):
    return random.choice(user_agents)

def is_account_under_review(user_id, proxies, user_agents):
    try:
        proxy, _ = get_random_proxy(proxies)
        headers = {
            "User-Agent": get_random_user_agent(user_agents),
            "Referer": f"https://www.tiktok.com/@dummy",
        }
        url = f"https://www.tiktok.com/@{user_id}"
        r = requests.get(url, headers=headers, proxies=proxy, timeout=TIMEOUT, verify=False)
        return r.status_code in [404, 451]
    except:
        return False

def report_user(user_id, reason, proxies, user_agents):
    for _ in range(RETRY_LIMIT):
        proxy_dict, proxy = get_random_proxy(proxies)
        headers = {
            "User-Agent": get_random_user_agent(user_agents),
            "Content-Type": "application/json",
        }
        data = {
            "reason": reason,
            "owner_id": user_id,
            "report_type": "user"
        }
        try:
            r = requests.post("https://www.tiktok.com/api/report/user/submit/?aid=1988",
                              headers=headers, json=data, proxies=proxy_dict,
                              timeout=TIMEOUT, verify=False)
            log(f"📨 Response {r.status_code} for {user_id}")
            if r.status_code == 200:
                save_log(SUCCESS_LOG, f"{user_id} | {proxy} | {datetime.now()}")
                return True
            elif r.status_code == 429:
                log("⚠️ Rate limited. Sleeping 10s...")
                time.sleep(10)
        except RequestException as e:
            log(f"❗ Error: {e}")
        time.sleep(DELAY)
    save_log(ERROR_LOG, f"{user_id} | {datetime.now()}")
    return False

def load_targets():
    targets = []
    if USE_BULK and os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].lstrip("@")
                targets.append(uid)
    else:
        uid = input("🎯 Enter target user ID to report: ").strip().lstrip("@")
        targets.append(uid)
    return targets

def worker(queue, proxies, user_agents, stats, lock):
    while not queue.empty():
        try:
            user_id = queue.get()
            if is_account_under_review(user_id, proxies, user_agents):
                log(f"⛔ {user_id} is under review. Skipping.")
            elif report_user(user_id, reason, proxies, user_agents):
                log(f"✅ Report sent for {user_id}")
                with lock:
                    stats["success"] += 1
                    report_count[user_id] = report_count.get(user_id, 0) + 1
                    log(f"📈 Total reports sent for {user_id}: {report_count[user_id]}")
            else:
                log(f"❌ Failed to report {user_id}")
                with lock:
                    stats["fail"] += 1
        finally:
            queue.task_done()

def run(targets):
    proxies = load_proxies()
    user_agents = load_user_agents()
    queue = Queue()
    stats = {"success": 0, "fail": 0}
    lock = threading.Lock()

    for t in targets:
        queue.put(t)

    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=worker, args=(queue, proxies, user_agents, stats, lock))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    log("📊 Summary:")
    log(f"Total: {len(targets)} | Success: {stats['success']} | Failed: {stats['fail']}")
    log("📊 Individual Report Counts:")
    for uid, count in report_count.items():
        log(f"{uid}: {count} reports sent")

if __name__ == "__main__":
    try:
        target_list = load_targets()
        while True:
            run(target_list)
            log(f"⏳ Waiting {DELAY * 2} seconds before next round...\n")
            time.sleep(DELAY * 2)
    except KeyboardInterrupt:
        log("🛑 Stopped by user.")
