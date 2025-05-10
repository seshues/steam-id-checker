import aiohttp
import asyncio
import json
import os
import random
import argparse
from datetime import datetime, timedelta, timezone

CONFIG_DIR = "config"
WORDLIST_DIR = "wordlists"
OUTPUT_DIR = "output"

with open(os.path.join(CONFIG_DIR, "config.json"), "r") as cfg:
    config = json.load(cfg)

API_KEY = config["api_key"]
CHECK_INTERVAL_DAYS = config.get("check_interval_days", 7)
LOG_FILE = config.get("log_file", os.path.join(OUTPUT_DIR, "activity.log"))
RETRY_DELAY = config.get("retry_delay", 1)
MAX_RETRIES = config.get("max_retries", 5)
SEM_LIMIT = config.get("sem_limit", 2)
IGNORE_SKIPLIST = config.get("ignore_skiplist", False)
IGNORE_CHECK_INTERVAL = config.get("ignore_check_interval", False)

PROFILE_API = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
GROUP_API = "https://steamcommunity.com/groups/{}/memberslistxml?xml=1"

parser = argparse.ArgumentParser(description="Steam vanity URL checker")
parser.add_argument("mode", choices=["profile", "group"], default="profile", nargs="?", help="Check type: profile or group")
parser.add_argument("--wordlist", default="wordlist.json", help="Name of the wordlist JSON file")
args = parser.parse_args()

MODE = args.mode
WORDLIST_FILE = os.path.join(WORDLIST_DIR, args.wordlist)
SKIPLIST_FILE = os.path.join(CONFIG_DIR, f"skiplist_{MODE}.json") # id's that are technically available but can't be set

valid_file = os.path.join(OUTPUT_DIR, f"valid_{MODE}.json")
invalid_file = os.path.join(OUTPUT_DIR, f"invalid_{MODE}.json")

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return default

def save_json(filename, data):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def log_activity(message):
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S] ")
    with open(LOG_FILE, "a") as log:
        log.write(timestamp + message + "\n")
    print(message)
    
async def handle_rate_limit(entity_type, vanity_url, delay):
    log_activity(f"[!] Rate limited on {entity_type}: {vanity_url}, retrying in {delay:.1f}s.")
    await asyncio.sleep(delay + random.uniform(0, 0.5))
    return delay * 2

async def check_id(session, vanity_url, valid_ids, invalid_ids, rate_limited_ids):
    try:
        vanity_url = vanity_url.lower()
        now = datetime.now(timezone.utc)

        if vanity_url in valid_ids:
            return

        if vanity_url in invalid_ids:
            if not IGNORE_CHECK_INTERVAL:
                last_checked = datetime.strptime(invalid_ids[vanity_url], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                days_ago = (now - last_checked).days
                if days_ago < CHECK_INTERVAL_DAYS:
                    log_activity(f"[~] Skipped id: {vanity_url}. Checked {days_ago} days ago.")
                    return

        if vanity_url in rate_limited_ids:
            last_rl = rate_limited_ids[vanity_url]
            if now - last_rl < timedelta(minutes=5):
                return

        delay = RETRY_DELAY
        for attempt in range(MAX_RETRIES):
            try:
                if MODE == "profile":
                    params = {"key": API_KEY, "vanityurl": vanity_url}
                    async with session.get(PROFILE_API, params=params) as resp:
                        if resp.status == 429:
                            rate_limited_ids[vanity_url] = now
                            delay = await handle_rate_limit("id", vanity_url, delay)
                            continue

                        if "application/json" not in resp.headers.get("Content-Type", ""):
                            log_activity(f"[!] Unexpected content type for id: {vanity_url}")
                            return

                        data = await resp.json()
                        result = data.get("response", {})
                        success = result.get("success")

                        if success == 1:
                            log_activity(f"[-] Unavailable: {vanity_url}")
                            invalid_ids[vanity_url] = now.strftime("%Y-%m-%d")
                        elif success == 42:
                            log_activity(f"[+] Available: {vanity_url}")
                            valid_ids.add(vanity_url)
                        else:
                            log_activity(f"[?] Unknown response for id: {vanity_url}: {result}")

                elif MODE == "group":
                    url = GROUP_API.format(vanity_url)
                    async with session.get(url) as resp:
                        if resp.status == 429:
                            rate_limited_ids[vanity_url] = now
                            delay = await handle_rate_limit("group id", vanity_url, delay)
                            continue

                        text = await resp.text()
                        if "<groupID64>" in text:
                            log_activity(f"[-] Unavailable: {vanity_url}")
                            invalid_ids[vanity_url] = now.strftime("%Y-%m-%d")
                        elif "No group could be retrieved for the given URL." in text:
                            log_activity(f"[+] Available: {vanity_url}")
                            valid_ids.add(vanity_url)
                        else:
                            log_activity(f"[?] Unknown response for group: {vanity_url}")

                rate_limited_ids.pop(vanity_url, None)
                return

            except aiohttp.ClientError as e:
                log_activity(f"[!] Network error on id: {vanity_url}: {e}, retrying in {delay:.1f}s...")
                await asyncio.sleep(delay + random.uniform(0, 0.5))
                delay *= 2

        log_activity(f"[!] Failed to check id: {vanity_url} after {MAX_RETRIES} retries.")
        
    except (ValueError, KeyError, TypeError) as e:
        log_activity(f"[!] Skipping id: {vanity_url} due to error: {e}")


async def run_with_semaphore(semaphore, *args):
    async with semaphore:
        await check_id(*args)

async def main():
    log_activity(f"[*] Running Steam vanity url checker with mode: {MODE}.")
        
    wordlist = sorted(set(w.lower() for w in load_json(WORDLIST_FILE, [])))
    skiplist = set()
    if not IGNORE_SKIPLIST:
        skiplist = set(w.lower() for w in load_json(SKIPLIST_FILE, []))
    else:
        log_activity("[~] Skiplist ignored due to config setting (ignore_skiplist = true).")
        
    valid_ids = set(w.lower() for w in load_json(valid_file, []))
    invalid_ids = {k.lower(): v for k, v in load_json(invalid_file, {}).items()}

    rate_limited_ids = {}
    semaphore = asyncio.Semaphore(SEM_LIMIT)
    
    filtered_wordlist = []
    for word in wordlist:
        word_lower = word.lower()
        if len(word_lower) < 3:
            log_activity(f"[~] Skipped id: (too short): {word}")
        elif not IGNORE_SKIPLIST and word_lower in skiplist:
            log_activity(f"[~] Skipped id: (in skiplist): {word}")
        else:
            filtered_wordlist.append(word_lower)


    async with aiohttp.ClientSession() as session:
        tasks = [
            run_with_semaphore(semaphore, session, vanity_url, valid_ids, invalid_ids, rate_limited_ids)
            for vanity_url in filtered_wordlist
        ]
        await asyncio.gather(*tasks)

    save_json(valid_file, list(valid_ids))
    save_json(invalid_file, invalid_ids)

    log_activity("[*] Check complete")
    log_activity(f"[+] Available: {len(valid_ids)}")
    log_activity(f"[-] Unavailable: {len(invalid_ids)}\n")

if __name__ == "__main__":
    asyncio.run(main())

