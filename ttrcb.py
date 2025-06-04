import requests, threading, random, time, json, os, csv
from queue import Queue
from datetime import datetime
from requests.exceptions import RequestException
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# === টার্মিনাল ইনপুট কনফিগারেশন শুরু ===
print("\n🔧 কনফিগারেশন লোড হচ্ছে টার্মিনাল থেকে...")

THREADS = int(input("থ্রেড সংখ্যা (ডিফল্ট 10): ") or 10)
RETRY_LIMIT = int(input("রিট্রাই সীমা (ডিফল্ট 3): ") or 3)
DELAY = int(input("ডিলে (সেকেন্ড): ") or 3)
TIMEOUT = int(input("টাইমআউট (সেকেন্ড): ") or 10)
USE_BULK = input("বাল্ক মোড ব্যবহার করবেন? (y/n): ").strip().lower() == 'y'
CSV_FILE = input("CSV ফাইলের নাম দিন (ডিফল্ট: targets.csv): ") or "targets.csv"

print("\n🎯 রিপোর্টের কারণ নির্বাচন করুন:")
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
reason = reason_map.get(input("নম্বর লিখুন (1–7): ").strip(), "nudity")

# === কনস্ট্যান্ট ===
PROXY_FILE = "working_proxies.txt"
USER_AGENT_FILE = "user_agents.txt"
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
            log(f"📨 {user_id} এর জন্য রেসপন্স কোড: {r.status_code}")
            if r.status_code == 200:
                save_log(SUCCESS_LOG, f"{user_id} | {proxy} | {datetime.now()}")
                return True
            elif r.status_code == 429:
                log("⚠️ রেট লিমিটে হিট হয়েছে। ১০ সেকেন্ড ঘুমাচ্ছে...")
                time.sleep(10)
        except RequestException as e:
            log(f"❗ ত্রুটি: {e}")
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
        uid = input("🎯 রিপোর্ট করতে যেই ইউজার আইডি চান: ").strip().lstrip("@")
        targets.append(uid)
    return targets

def worker(queue, proxies, user_agents, stats, lock):
    while not queue.empty():
        try:
            user_id = queue.get()
            if is_account_under_review(user_id, proxies, user_agents):
                log(f"⛔ {user_id} রিভিউতে আছে। স্কিপ করা হলো।")
            elif report_user(user_id, reason, proxies, user_agents):
                log(f"✅ রিপোর্ট সফল হয়েছে: {user_id}")
                with lock:
                    stats["success"] += 1
            else:
                log(f"❌ রিপোর্ট ব্যর্থ হয়েছে: {user_id}")
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

    log("📊 সারসংক্ষেপ:")
    log(f"মোট: {len(targets)} | সফল: {stats['success']} | ব্যর্থ: {stats['fail']}")

if __name__ == "__main__":
    try:
        while True:
            run()
            log(f"⏳ {DELAY * 2} সেকেন্ড অপেক্ষা করা হচ্ছে পরবর্তী রাউন্ডের আগে...\n")
            time.sleep(DELAY * 2)
    except KeyboardInterrupt:
        log("🛑 ইউজার দ্বারা বন্ধ করা হয়েছে।")
