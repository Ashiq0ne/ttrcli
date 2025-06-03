import requests
import concurrent.futures
from datetime import datetime

# Proxy sources (HTTP only)
proxy_sources = [
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt"
]

# Output files
ALL_PROXIES_FILE = "all_proxies.txt"
WORKING_PROXIES_FILE = "working_proxies.txt"

# Settings
MAX_THREADS = 100
CHECK_TIMEOUT = 5  # seconds
TEST_URL = "http://www.google.com"

def fetch_proxies():
    proxies = set()
    print("[+] Fetching proxies...")
    for url in proxy_sources:
        try:
            r = requests.get(url, timeout=10)
            lines = r.text.strip().splitlines()
            for line in lines:
                if ':' in line:
                    proxies.add(line.strip())
        except Exception as e:
            print(f"[-] Failed to fetch from {url}: {e}")
    print(f"[✓] Fetched {len(proxies)} total proxies.\n")
    return list(proxies)

def test_proxy(proxy):
    try:
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        r = requests.get(TEST_URL, proxies=proxies, timeout=CHECK_TIMEOUT)
        if r.status_code == 200:
            print(f"[✓] Working: {proxy}")
            return proxy
    except:
        pass
    return None

def check_proxies(proxies):
    working = []
    print("[*] Checking proxies...\n")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        results = executor.map(test_proxy, proxies)
        for result in results:
            if result:
                working.append(result)
    return working

def save_to_file(filename, proxy_list):
    with open(filename, "w") as f:
        for p in proxy_list:
            f.write(p + "\n")

if __name__ == "__main__":
    print(f"==== Proxy Fetch + Checker ====\n{datetime.now()}\n")
    all_proxies = fetch_proxies()
    save_to_file(ALL_PROXIES_FILE, all_proxies)
    working = check_proxies(all_proxies)
    save_to_file(WORKING_PROXIES_FILE, working)
    print(f"\n=== Done ===")
    print(f"Total fetched: {len(all_proxies)}")
    print(f"Working proxies: {len(working)}")
    print(f"Saved to '{WORKING_PROXIES_FILE}' ✅")
