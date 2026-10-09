#!/usr/bin/env python3
# ASCII USERNAME CHECKER V10.0
# Python 3.8+ | Pydroid 3 | Standard library only

import csv
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

APP_NAME = "ASCII USERNAME CHECKER"
VERSION = "10.0"
MAX_BATCH = 100

DATA_DIR = Path.home() / "ASCII_Username_Checker"
HISTORY_FILE = DATA_DIR / "history.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

PLATFORMS = {
    "github": {
        "name": "GitHub",
        "pattern": r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$",
        "note": "1-39 chars; letters, numbers, internal hyphens.",
    },
    "gitlab": {
        "name": "GitLab",
        "pattern": r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,253}$",
        "note": "Approximate format; platform rules may vary.",
    },
    "reddit": {
        "name": "Reddit",
        "pattern": r"^[A-Za-z0-9_-]{3,20}$",
        "note": "3-20 chars; letters, numbers, _ and -.",
    },
    "discord": {
        "name": "Discord",
        "pattern": r"^[a-z0-9._]{2,32}$",
        "note": "Approximate format; platform rules may vary.",
    },
}

DEFAULT_SETTINGS = {
    "timeout": 8,
    "delay": 1.2,
    "retries": 1,
    "history": True,
}


def banner():
    print(r"""
     _    ____   ____ ___ ___
    / \  / ___| / ___|_ _|_ _|
   / _ \ \___ \| |    | | | |
  / ___ \ ___) | |___ | | | |
 /_/   \_\____/ \____|___|___|

       USERNAME CHECKER
    """)
    print("  VERSION " + VERSION)
    print("  Format | Public API | Batch | Export")
    print("=" * 48)


def setup():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    try:
        setup()
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        return True
    except OSError as error:
        print("[!] Save error:", error)
        return False


def settings_load():
    settings = DEFAULT_SETTINGS.copy()
    settings.update(load_json(SETTINGS_FILE, {}))

    try:
        settings["timeout"] = max(
            2, min(30, float(settings["timeout"]))
        )
        settings["delay"] = max(
            0.5, min(10, float(settings["delay"]))
        )
        settings["retries"] = max(
            0, min(3, int(settings["retries"]))
        )
        settings["history"] = bool(settings["history"])
    except (TypeError, ValueError):
        settings = DEFAULT_SETTINGS.copy()

    return settings


def clean_username(value):
    return value.strip().lstrip("@").strip()


def input_valid(username):
    if not username:
        return False, "Username cannot be empty."
    if len(username) > 254:
        return False, "Username is too long."
    if any(char.isspace() for char in username):
        return False, "Spaces are not allowed."
    if "/" in username or "\\" in username:
        return False, "Enter a username, not a URL."
    return True, "OK"


def analyze_name(username):
    notes = []
    score = 100

    if len(username) < 3:
        notes.append("Very short username.")
        score -= 25

    if len(username) > 20:
        notes.append("Long username.")
        score -= 5

    if re.search(r"(.)\1{3,}", username):
        notes.append("Repeated characters detected.")
        score -= 15

    if re.search(r"\d{5,}", username):
        notes.append("Long number sequence detected.")
        score -= 10

    if username.isdigit():
        notes.append("Username contains numbers only.")
        score -= 20

    if username.lower() in {
        "admin", "administrator", "root",
        "official", "support", "moderator"
    }:
        notes.append("Common or reserved-looking name.")
        score -= 15

    if not notes:
        notes.append("No obvious naming-pattern flags.")

    return max(0, score), notes


def api_request(url, settings):
    headers = {
        "User-Agent": "ASCII-Username-Checker/10.0",
        "Accept": "application/json",
    }

    request = urllib.request.Request(
        url, headers=headers, method="GET"
    )

    attempts = settings["retries"] + 1

    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                request, timeout=settings["timeout"]
            ) as response:
                raw = response.read(1024 * 1024)
                return json.loads(
                    raw.decode("utf-8", errors="replace")
                ), response.status, ""

        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None, 404, "Not found."

            if error.code in (403, 429):
                return None, error.code, (
                    "Rate limited or temporarily restricted."
                )

            if error.code >= 500 and attempt + 1 < attempts:
                time.sleep(attempt + 1)
                continue

            return None, error.code, "HTTP error."

        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
        ) as error:
            if attempt + 1 < attempts:
                time.sleep(attempt + 1)
                continue
            return None, None, "Request failed: " + str(error)

    return None, None, "Request failed."


def check_username(username, platform, settings):
    info = PLATFORMS[platform]
    valid, message = input_valid(username)

    result = {
        "username": username,
        "platform": info["name"],
        "time": datetime.now().isoformat(timespec="seconds"),
        "format_valid": False,
        "status": "UNKNOWN",
        "details": "",
        "profile_url": "",
    }

    if not valid:
        result["details"] = message
        return result

    result["format_valid"] = bool(
        re.fullmatch(info["pattern"], username)
    )

    if not result["format_valid"]:
        result["status"] = "INVALID FORMAT"
        result["details"] = info["note"]
        return result

    encoded = urllib.parse.quote(username, safe="")

    if platform == "github":
        url = "https://api.github.com/users/" + encoded
        data, code, error = api_request(url, settings)

        if code == 200 and isinstance(data, dict):
            result["status"] = "TAKEN"
            result["profile_url"] = "https://github.com/" + encoded
            result["details"] = "Public GitHub profile found."

        elif code == 404:
            result["status"] = "NOT FOUND"
            result["details"] = (
                "No public profile found. Registration availability "
                "is not guaranteed."
            )

        else:
            result["status"] = "UNKNOWN"
            result["details"] = error

    elif platform == "gitlab":
        url = (
            "https://gitlab.com/api/v4/users?username=" + encoded
        )
        data, code, error = api_request(url, settings)

        if code == 200 and isinstance(data, list):
            match = any(
                isinstance(item, dict)
                and str(item.get("username", "")).casefold()
                == username.casefold()
                for item in data
            )

            if match:
                result["status"] = "TAKEN"
                result["profile_url"] = (
                    "https://gitlab.com/" + encoded
                )
                result["details"] = "Matching public user found."
            else:
                result["status"] = "NOT FOUND"
                result["details"] = (
                    "No exact match returned. Availability "
                    "is not guaranteed."
                )
        else:
            result["status"] = "UNKNOWN"
            result["details"] = error

    else:
        result["status"] = "FORMAT ONLY"
        result["details"] = (
            "Live availability is not checked for this platform."
        )

    return result


def show_result(result):
    print("\n" + "-" * 48)
    print("Username :", result["username"])
    print("Platform :", result["platform"])
    print("Format   :", "VALID" if result["format_valid"]
          else "INVALID")
    print("Status   :", result["status"])
    print("Details  :", result["details"])

    if result["profile_url"]:
        print("Profile  :", result["profile_url"])

    print("-" * 48)


def choose_platform():
    keys = list(PLATFORMS)

    print("\nPLATFORMS")
    for number, key in enumerate(keys, 1):
        print(str(number) + ". " + PLATFORMS[key]["name"])

    print("5. All platforms")

    while True:
        choice = input("Select [1-5]: ").strip()

        if choice in ("1", "2", "3", "4"):
            return [keys[int(choice) - 1]]

        if choice == "5":
            return keys

        print("[!] Invalid selection.")


def record_history(result, settings):
    if not settings["history"]:
        return

    history = load_json(HISTORY_FILE, [])
    history.append(result)
    save_json(HISTORY_FILE, history[-500:])


def single_check(settings):
    username = clean_username(input("Enter username: "))
    platforms = choose_platform()
    results = []

    for index, platform in enumerate(platforms):
        result = check_username(username, platform, settings)
        show_result(result)
        record_history(result, settings)
        results.append(result)

        if index < len(platforms) - 1:
            time.sleep(settings["delay"])

    return results


def batch_names():
    print("\n1. Enter usernames")
    print("2. Read a text file")
    mode = input("Choose [1-2]: ").strip()

    if mode == "2":
        path = Path(
            input("File path: ").strip().strip('"')
        ).expanduser()

        try:
            with path.open(
                "r", encoding="utf-8-sig", errors="replace"
            ) as file:
                values = [
                    clean_username(line)
                    for line in file
                    if line.strip() and not line.lstrip().startswith("#")
                ]
        except OSError as error:
            print("[!] File error:", error)
            return []

    else:
        raw = input("Usernames separated by commas/spaces: ")
        values = [
            clean_username(item)
            for item in re.split(r"[,;\s]+", raw)
            if item.strip()
        ]

    return list(dict.fromkeys(values))[:MAX_BATCH]


def export_results(results):
    if not results:
        print("[!] No results to export.")
        return

    setup()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("1. JSON")
    print("2. CSV")
    choice = input("Export format: ").strip()

    try:
        if choice == "1":
            path = DATA_DIR / ("results_" + stamp + ".json")
            with path.open("w", encoding="utf-8") as file:
                json.dump(results, file, indent=2)
        elif choice == "2":
            path = DATA_DIR / ("results_" + stamp + ".csv")
            with path.open(
                "w", newline="", encoding="utf-8"
            ) as file:
                writer = csv.DictWriter(
                    file, fieldnames=list(results[0].keys())
                )
                writer.writeheader()
                writer.writerows(results)
        else:
            print("[!] Cancelled.")
            return

        print("[+] Saved to:", path)

    except OSError as error:
        print("[!] Export error:", error)


def batch_check(settings):
    names = batch_names()

    if not names:
        print("[!] No usernames entered.")
        return []

    platforms = choose_platform()
    total = len(names) * len(platforms)
    results = []
    count = 0

    print("\nChecking", len(names), "username(s).")

    for username in names:
        for platform in platforms:
            count += 1
            print(
                "\n[" + str(count) + "/" + str(total) + "]",
                username,
            )

            result = check_username(username, platform, settings)
            show_result(result)
            record_history(result, settings)
            results.append(result)

            if count < total:
                time.sleep(settings["delay"])

    export_results(results)
    return results


def idea_generator():
    base = clean_username(input("Base word/theme: "))
    base = re.sub(r"[^A-Za-z0-9_-]", "", base)[:18]

    if not base:
        print("[!] Enter letters or numbers.")
        return

    prefixes = ["Neo", "Its", "Real", "The", "Ultra", "Next"]
    suffixes = [
        "HQ", "Nova", "Orbit", "Pixel", "Byte",
        "Echo", "Quest", "Labs", "Zone", "Dev"
    ]

    ideas = [
        base + random.choice(suffixes),
        random.choice(prefixes) + base.title(),
        base + str(random.randint(10, 999)),
        base + "_" + random.choice(["dev", "plays", "hub"]),
        base.title() + random.choice(["Studio", "World", "Verse"]),
    ]

    print("\nUSERNAME IDEAS")
    for idea in dict.fromkeys(ideas):
        print("  > " + idea)


def style_analyzer():
    username = clean_username(input("Username: "))
    valid, message = input_valid(username)

    if not valid:
        print("[!]", message)
        return

    score, notes = analyze_name(username)

    print("\nSTYLE ANALYSIS")
    print("Length:", len(username))
    print("Heuristic score:", str(score) + "/100")
    print("(This is not a security or availability score.)")

    for note in notes:
        print("  -", note)


def view_history():
    history = load_json(HISTORY_FILE, [])

    if not history:
        print("[i] No history found.")
        return

    print("\nRECENT HISTORY")
    for item in reversed(history[-20:]):
        print(
            item.get("time", "?"),
            "|",
            item.get("platform", "?"),
            "|",
            item.get("username", "?"),
            "|",
            item.get("status", "?"),
        )


def settings_menu(settings):
    while True:
        print("\nSETTINGS")
        print("1. Timeout:", settings["timeout"])
        print("2. Request delay:", settings["delay"])
        print("3. Retries:", settings["retries"])
        print("4. Toggle history:", settings["history"])
        print("5. Save and return")

        choice = input("Choice: ").strip()

        try:
            if choice == "1":
                settings["timeout"] = max(
                    2, min(30, float(input("Timeout 2-30: ")))
                )
            elif choice == "2":
                settings["delay"] = max(
                    0.5, min(10, float(input("Delay 0.5-10: ")))
                )
            elif choice == "3":
                settings["retries"] = max(
                    0, min(3, int(input("Retries 0-3: ")))
                )
            elif choice == "4":
                settings["history"] = not settings["history"]
            elif choice == "5":
                save_json(SETTINGS_FILE, settings)
                return settings
            else:
                print("[!] Invalid choice.")
        except ValueError:
            print("[!] Enter a valid number.")


def help_menu():
    print("""
ASCII USERNAME CHECKER V10

FEATURES
- Username format validation
- Public API profile checks for GitHub and GitLab
- Format-only checks for Reddit and Discord
- Batch checks, up to 100 unique names
- Text-file input
- JSON and CSV exports
- Username style analysis and idea generation
- Local history and adjustable settings

STATUS MEANINGS
TAKEN       - A matching public profile was found.
NOT FOUND   - No public profile was returned; availability is not guaranteed.
UNKNOWN     - A network, API, or rate-limit issue prevented confirmation.
FORMAT ONLY - The format was checked, not live availability.

PRIVACY
- Usernames checked against APIs are sent to those services.
- History and exports are saved locally.
- No passwords, tokens, login bypass, or account creation.
- Use reasonable delays and respect platform rules.

PYDROID 3
No pip installation is required.
""")


def main():
    setup()
    settings = settings_load()
    last_results = []

    while True:
        os.system("cls" if os.name == "nt" else "clear")
        banner()

        print("\nMAIN MENU")
        print("1. Single username check")
        print("2. Batch username checker")
        print("3. Username style analyzer")
        print("4. Username idea generator")
        print("5. View history")
        print("6. Export last results")
        print("7. Settings")
        print("8. Help")
        print("0. Exit")

        choice = input("\nASCII > ").strip()

        try:
            if choice == "1":
                last_results = single_check(settings)
            elif choice == "2":
                last_results = batch_check(settings)
            elif choice == "3":
                style_analyzer()
            elif choice == "4":
                idea_generator()
            elif choice == "5":
                view_history()
            elif choice == "6":
                export_results(last_results)
            elif choice == "7":
                settings = settings_menu(settings)
            elif choice == "8":
                help_menu()
            elif choice == "0":
                print("ASCII Username Checker closed.")
                break
            else:
                print("[!] Invalid option.")

        except KeyboardInterrupt:
            print("\n[!] Operation cancelled.")

        if choice != "0":
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting ASCII Username Checker.")
    except EOFError:
        print("\nInput ended.")
