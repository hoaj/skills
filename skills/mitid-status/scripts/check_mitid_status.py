#!/usr/bin/env python3
"""
Check current MitID drift status from digitaliser.dk.

Usage:
    python check_mitid_status.py           # current status only
    python check_mitid_status.py --news    # include latest news/updates
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)


SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})
TIMEOUT = 10


# --- Current status (parsed from server-rendered HTML) ---

class StatusParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_mitid_section = False
        self._in_status_span = False
        self._buf = []
        self.status_class = None
        self.status_text = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "a" and attr_dict.get("href") == "/mitid":
            self._in_mitid_section = True
        if self._in_mitid_section:
            if tag == "div" and attr_dict.get("data-servicevariable") == "Class":
                self.status_class = attr_dict.get("class", "")
            elif tag == "span" and attr_dict.get("class") == "info":
                self._in_status_span = True
                self._buf = []

    def handle_endtag(self, tag):
        if self._in_status_span and tag == "span":
            self.status_text = "".join(self._buf).strip()
            self._in_status_span = False
            self._in_mitid_section = False

    def handle_data(self, data):
        if self._in_status_span:
            self._buf.append(data)


def get_current_status():
    resp = SESSION.get("https://www.digitaliser.dk/driftsstatus", timeout=TIMEOUT)
    resp.raise_for_status()

    parser = StatusParser()
    parser.feed(resp.text)

    text = parser.status_text or "Unknown"
    if ": " in text:
        text = text.split(": ", 1)[1]

    return {
        "service": "MitID",
        "status_text": text,
        "is_available": parser.status_class == "status-ok",
        "raw_class": parser.status_class,
    }


# --- Latest news/updates (via proxy.gba API) ---

# Base64-encoded GoBasic filter for MitID news (content IDs: 6323, 7013, 7006, 7012, 7533, 6320)
MITID_CONTEXT = (
    "eyJzaXRlU2VhcmNoIjogZmFsc2UsICJwZGZTZWFyY2giOiB0cnVlLCAiY29udGV4dFBhdGgi"
    "OiAiIiwgImZpbHRlciI6IHsidCI6IFsiTmV3c1BhZ2UiXSwgImRmIjogIjAxLTAxLTIwMjQi"
    "LCAiZHQiOiAiMzEtMTItMjAyNiIsICJjaWRzIjogWyI2MzIzIiwgIjcwMTMiLCAiNzAwNiIs"
    "ICI3MDEyIiwgIjc1MzMiLCAiNjMyMCJdLCAiciI6IHRydWUsICJleGFjdE1hdGNoIjogZmFs"
    "c2UsICJjbyI6ICJPciIsICJjdG8iOiAiQW5kIiwgImUiOiBbeyJ0eXBlIjogIk5vdFF1ZXJ5"
    "IiwgInEiOiB7InR5cGUiOiAiVGVybVF1ZXJ5IiwgImZuIjogIl9faWQiLCAidiI6ICI2ODky"
    "In19XX0sICJvcHRpb25zIjogeyJzaG93VGVhc2VyIjogdHJ1ZSwgInRlYXNlclRleHRMZW5n"
    "dGgiOiAxNjAsICJzaG93Q2F0ZWdvcml6YXRpb25zIjogdHJ1ZSwgInNob3dEYXRlIjogdHJ1"
    "ZSwgImRvTm90U2hvd0luaXRpYWxSZXN1bHRzIjogZmFsc2UsICJkaXNwbGF5UmVjb3JkVHlw"
    "ZUZpbHRlciI6IGZhbHNlLCAiaW5jbHVkZVBpbm5lZFNlYXJjaFF1ZXJpZXMiOiBmYWxzZSwg"
    "InNob3dSc3NMaW5rIjogZmFsc2UsICJtYXhJdGVtc1Nob3duIjogMTAsICJncm91cEJ5Ijog"
    "Ik5vR3JvdXBpbmciLCAic2hvd1BhZ2VyIjogZmFsc2UsICJzaG93TG9hZE1vcmUiOiBmYWxz"
    "ZSwgImFyY2hpdmVMaW5rIjogIjxhPjwvYT4iLCAicnNzVGl0bGUiOiAiIiwgInJzc0Rlc2Ny"
    "aXB0aW9uIjogIiIsICJzaG93VGh1bWJuYWlscyI6IHRydWUsICJzaG93QWJzb2x1dGVVcmwi"
    "OiBmYWxzZSwgInRyYW5zbGF0aW9uRm9sZGVyIjogIkR5bmFtaWMgTGlzdCBNb2R1bGUiLCAi"
    "c291cmNlUGF0aCI6ICIiLCAic2hvd0Zvcm1hdHRlZFVybCI6IGZhbHNlLCAiZmVhdHVyZWRJ"
    "dGVtSWRzIjogIiIsICJjb2x1bW5TcGFuIjogNiwgImNvbHVtbnMiOiAxLCAicmVzVHh0Tm9u"
    "ZSI6ICIiLCAicmVzVHh0U2luZ3VsYXIiOiAiIiwgInJlc1R4dFBsdXJhbCI6ICIiLCAic29y"
    "dGluZyI6ICIiLCAiaGVhZGxpbmVFbXB0eSI6IGZhbHNlLCAib3BlbkxpbmtzSW5Qb3B1cFdp"
    "bmRvdyI6IGZhbHNlLCAiY2hhbmdlRnJvbUgyVG9IMSI6IGZhbHNlLCAiZG9Ob3RTaG93T2xk"
    "RG9jdW1lbnRzIjogZmFsc2UsICJvcGVuZWRMaW5rc0Rpc3BsYXlNb2RlIjogIk9wZW5MaW5r"
    "c0luVGhlU2FtZVdpbmRvdyIsICJkaXNwbGF5RXhhY3RNYXRjaFNlYXJjaENoZWNrYm94Ijog"
    "ZmFsc2UsICJkaXNwbGF5U29ydEJ5UmVsZXZhbmNlT3JEYXRlIjogZmFsc2V9fQ=="
)

# Cache hash for the above context (SHA256, used by GoBasic for HTTP caching)
MITID_HASH = "fbd212405d7efab56bd1e1cd7743bd13099bfc8582405a0f7e4efb8d7d0d0862"


class NewsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self._current = {}
        self._in_item = False
        self._in_heading = False
        self._in_date = False
        self._in_label = False
        self._in_teaser = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")
        if "item" in cls.split():
            self._current = {"title": None, "url": None, "date": None, "labels": [], "teaser": None}
            self._in_item = True
        if self._in_item:
            if tag == "a":
                self._current["url"] = attr_dict.get("href")
                self._in_heading = True
                self._buf = []
            elif tag == "span" and cls == "date":
                self._in_date = True
                self._buf = []
            elif tag == "span" and cls == "label":
                self._in_label = True
                self._buf = []
            elif tag == "p":
                self._in_teaser = True
                self._buf = []

    def handle_endtag(self, tag):
        if self._in_heading and tag == "a":
            self._current["title"] = "".join(self._buf).strip()
            self._in_heading = False
        elif self._in_date and tag == "span":
            self._current["date"] = "".join(self._buf).strip()
            self._in_date = False
        elif self._in_label and tag == "span":
            self._current["labels"].append("".join(self._buf).strip())
            self._in_label = False
        elif self._in_teaser and tag == "p":
            self._current["teaser"] = "".join(self._buf).strip()
            self._in_teaser = False
        elif self._in_item and tag == "div" and self._current.get("title"):
            self.items.append(dict(self._current))
            self._in_item = False

    def handle_data(self, data):
        if self._in_heading or self._in_date or self._in_label or self._in_teaser:
            self._buf.append(data)


def get_latest_news():
    payload = {
        "control": "GoBasic.Presentation.Controls.ListHelper, GoBasic.Presentation",
        "method": "GetPage",
        "path": "/mitid",
        "query": "",
        "args": {
            "arg0": {
                "options": {
                    "generator": "GoBasic.Presentation.Controls.ListHelper, GoBasic.Presentation",
                    "dateRange": False,
                },
                "context": MITID_CONTEXT,
                "hash": MITID_HASH,
            },
            "arg1": 1,
            "arg2": {"categorizations": []},
            "arg3": "",
        },
    }

    resp = SESSION.post(
        "https://www.digitaliser.dk/mitid/proxy.gba",
        headers={
            "Content-Type": "versus/callback; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-Cacheable": "true",
        },
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

    parser = NewsParser()
    parser.feed(resp.json()["value"]["page"])

    seen = set()
    items = []
    for item in parser.items:
        if item["url"] not in seen and "MitID" in item.get("labels", []):
            seen.add(item["url"])
            items.append(item)
    return items


# --- Main ---

def main():
    arg_parser = argparse.ArgumentParser(description="Check MitID drift status from digitaliser.dk")
    arg_parser.add_argument("--news", action="store_true", help="Also fetch latest news/updates")
    arg_parser.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")
    args = arg_parser.parse_args()

    if args.news:
        with ThreadPoolExecutor(max_workers=2) as pool:
            status_future = pool.submit(get_current_status)
            news_future = pool.submit(get_latest_news)
        status = status_future.result()
        news = news_future.result()
    else:
        status = get_current_status()
        news = None

    if args.as_json:
        result = {"status": status}
        if news is not None:
            result["news"] = news
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    icon = "✅" if status["is_available"] else "❌"
    print(f"{icon}  MitID: {status['status_text']}")

    if news is not None:
        print()
        if not news:
            print("No recent MitID updates found.")
        else:
            print("Latest MitID updates:")
            for item in news[:5]:
                print(f"  [{item['date']}] {item['title']}")
                if item["teaser"]:
                    print(f"             {item['teaser'][:100]}...")
                print(f"             {item['url']}")


if __name__ == "__main__":
    main()
