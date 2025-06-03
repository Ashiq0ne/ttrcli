import requests, threading, random, time, os, csv
from queue import Queue
from datetime import datetime
from requests.exceptions import RequestException
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Terminal Input
print("\n TikTok Reporter CLI")
REASON = input("   (: nudity, harassment): ").strip()
MODE = input("Bulk mode    'y' ,      : ").lower()

if MODE == 'y':
    CSV_FILE = input("CSV   (default: targets.csv): ").strip() or "targets.csv"
else:
    SINGLE_USER = input("     (@ ): ").strip().lstrip("@")

PROXY_FILE = input("   (default: working_proxies.txt): ").strip() or "working_proxies.txt"
USER_AGENT_FILE = input("User-Agent   (optional, press Enter to skip): ").strip()

THREADS = int(input("Thread  (default: 10): ") or 10)
RETRY_LIMIT = int(input("     ? (default: 3): ") or 3)
DELAY = int(input("      ? (default: 3): ") or 3)
TIMEOUT = int(input("  (default: 10 ): ") or 10)

LOG_FILE = "report_log.txt"
SUCCESS_LOG = "logs/success_log.txt"
ERROR_LOG = "logs/error_log.txt"
os.makedirs("logs", exist_ok=True)

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
    if USER_AGENT_FILE and os.path.exists(USER_AGENT_FILE):
        with open(USER_AGENT_FILE) as f:
            return [ua.strip() for ua in f if ua.strip()]
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    ]

def get_random_proxy(proxies):
    proxy = random.choice(proxies)
    return {"http": f"http://{proxy}", "https": f"http://{proxy}"}, proxy

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
            log(f"Status {r.status_code} for {user_id}")
            if r.status_code == 200:
                save_log(SUCCESS_LOG, f"{user_id} | {proxy} | {datetime.now()}")
                return True
            elif r.status_code == 429:
                log("Rate limit hit. Sleeping 60s")
                time.sleep(60)
        except RequestException as e:
            log(f"Error: {e}")
        time.sleep(DELAY)
    save_log(ERROR_LOG, f"{user_id} | {datetime.now()}")
    return False

def load_targets():
    targets = []
    if MODE == 'y' and os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].lstrip("@")
                targets.append(uid)
    else:
        targets.append(SINGLE_USER)
    return targets

def worker(queue, proxies, user_agents, stats, lock):
    while not queue.empty():
        try:
            user_id = queue.get()
            if is_account_under_review(user_id, proxies, user_agents):
                log(f" {user_id} is under cover. Skipping.")
            elif report_user(user_id, REASON, proxies, user_agents):
                log(f" Report sent for {user_id}")
                with lock:
                    stats["success"] += 1
            else:
                log(f" Failed for {user_id}")
                with lock:
                    stats["fail"] += 1
        finally:
            queue.task_done()

def run():
    proxies = load_proxies()
    user_agents = load_user_agents()
    targets = load_targets()
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

    log("\n Summary:")
    log(f"Total: {len(targets)} | Success: {stats['success']} | Failed: {stats['fail']}")

if __name__ == "__main__":
    try:
        while True:
            run()
            log(f"Sleeping {DELAY * 5}s before next round...\n")
            time.sleep(DELAY * 5)
    except KeyboardInterrupt:
        log(" Stopped by user.")
