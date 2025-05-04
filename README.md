# Steam ID Checker

Python script that checks for available Steam IDs for **user profiles** and **groups**.

---

## Features

- Supports checking for both **profile** and **group** IDs
- Logging to file and console
- Skiplist support to avoid checking known unassignable IDs
- Configurable via `config/config.json`
- Output saves available/unavailable IDs separately

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/seshues/steam-id-checker.git
cd steam-id-checker
```

### 2. Install aiohttp
```bash
pip install aiohttp
```

### 3. Edit config/config.json and add your Steam Web API key:
```json
{
    "api_key": "YOUR_STEAM_API_KEY_HERE",
    "check_interval_days": 7,
    "log_file": "activity.log",
    "retry_delay": 1,
    "max_retries": 5,
    "sem_limit": 2,
    "ignore_skiplist": false
}
```

---

## Usage
```bash
python steam-id-checker.py [mode] --wordlist [filename]
```

### Arguments:

- mode: profile (default) or group
- --wordlist: Optional. Defaults to wordlist.json

### Example:
```bash
python steam-id-checker.py
python steam-id-checker.py --wordlist list.json
python steam-id-checker.py group
python steam-id-checker.py profile --wordlist list.json
```

---

## Skiplist Behavior

By default, the script skips IDs listed in config/skiplist_profile.json or config/skiplist_group.json. To override this behavior, set ignore_skipfile: true in your config file.

---

## Output

- Available IDs are saved in output/valid_profile.json or valid_group.json
- Unavailable IDs are saved in output/invalid_profile.json or invalid_group.json
- Logs are saved to the path defined in log_file. (defaults to folder where script is ran in)
