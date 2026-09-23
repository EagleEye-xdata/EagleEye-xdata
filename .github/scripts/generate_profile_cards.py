"""Generate dark/light GitHub profile SVG cards without an external stats host."""
from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USER = os.environ["GITHUB_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("dist")
OUT.mkdir(exist_ok=True)
API = "https://api.github.com"

THEMES = {
    "dark": {"bg": "#0D1117", "panel": "#161B22", "text": "#E6EDF3", "muted": "#8B949E", "cyan": "#00F0FF", "purple": "#A855F7", "green": "#39FF14", "grid": "#30363D"},
    "light": {"bg": "#FFFFFF", "panel": "#F6F8FA", "text": "#0D1117", "muted": "#57606A", "cyan": "#007C87", "purple": "#7C2BD4", "green": "#1A8F0A", "grid": "#D0D7DE"},
}


def request(url: str, body: dict | None = None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {TOKEN}", "User-Agent": "EagleEye-xdata-profile-cards"}
    payload = json.dumps(body).encode() if body else None
    if body:
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, payload, headers), timeout=30) as response:
        return json.loads(response.read())


def graphql(query: str, variables: dict) -> dict:
    result = request("https://api.github.com/graphql", {"query": query, "variables": variables})
    if "errors" in result:
        raise RuntimeError(result["errors"])
    return result["data"]


def card(title: str, body: str, theme: dict) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="260" viewBox="0 0 700 260" role="img" aria-label="{html.escape(title)}">
<rect width="700" height="260" rx="18" fill="{theme['bg']}"/><rect x="1" y="1" width="698" height="258" rx="17" fill="none" stroke="{theme['grid']}"/>
<text x="32" y="48" fill="{theme['cyan']}" font-family="Fira Code, monospace" font-size="21" font-weight="700">{html.escape(title)}</text>{body}</svg>'''


def save(name: str, render) -> None:
    for variant, theme in THEMES.items():
        suffix = "-dark" if variant == "dark" else ""
        (OUT / f"{name}{suffix}.svg").write_text(render(theme), encoding="utf-8")


query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) { followers { totalCount } repositories(first: 1, privacy: PUBLIC) { totalCount }
    contributionsCollection(from: $from, to: $to) { contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } } }
  }
}"""
# GitHub runners use UTC. Use IST calendar boundaries so a contribution made after
# midnight in India is rendered as the current IST day, rather than yesterday UTC.
IST = timezone(timedelta(hours=5, minutes=30))
now = datetime.now(IST)
range_start = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
range_end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
data = graphql(query, {"login": USER, "from": range_start.isoformat(), "to": range_end.isoformat()})["user"]
calendar = data["contributionsCollection"]["contributionCalendar"]
days = [item for week in calendar["weeks"] for item in week["contributionDays"]]
contribution_total = sum(item["contributionCount"] for item in days)
repos = request(f"{API}/users/{USER}/repos?per_page=100&type=owner")
stars = sum(repo["stargazers_count"] for repo in repos)
languages = Counter()
for repo in repos:
    if not repo.get("fork"):
        try:
            languages.update(request(repo["languages_url"]))
        except Exception:
            pass


def draw_stats(t):
    stats = [("CONTRIBUTIONS", contribution_total, t["cyan"]), ("PUBLIC REPOS", data["repositories"]["totalCount"], t["purple"]), ("FOLLOWERS", data["followers"]["totalCount"], t["green"]), ("STARS", stars, t["cyan"])]
    body = ""
    for index, (label, value, color) in enumerate(stats):
        x = 40 + index * 165
        body += f'<rect x="{x}" y="78" width="142" height="132" rx="12" fill="{t["panel"]}"/><text x="{x+71}" y="137" text-anchor="middle" fill="{color}" font-family="Fira Code, monospace" font-size="35" font-weight="700">{value}</text><text x="{x+71}" y="174" text-anchor="middle" fill="{t["muted"]}" font-family="Arial, sans-serif" font-size="12">{label}</text>'
    return card("github_stats --year", body, t)


def draw_languages(t):
    items = languages.most_common(5)
    total = max(sum(languages.values()), 1)
    colors = [t["cyan"], t["purple"], t["green"], "#F59E0B", "#F43F5E"]
    body = ""
    for index, (language, amount) in enumerate(items):
        y = 83 + index * 30
        percent = amount / total * 100
        body += f'<text x="36" y="{y+14}" fill="{t["text"]}" font-family="Fira Code, monospace" font-size="14">{html.escape(language)}</text><rect x="215" y="{y}" width="390" height="16" rx="8" fill="{t["grid"]}"/><rect x="215" y="{y}" width="{max(4, 390*percent/100):.1f}" height="16" rx="8" fill="{colors[index]}"/><text x="650" y="{y+14}" text-anchor="end" fill="{t["muted"]}" font-family="Fira Code, monospace" font-size="12">{percent:.1f}%</text>'
    return card("top_languages --owned-repos", body, t)


counts = {entry["date"]: entry["contributionCount"] for entry in days}
today = now.date()
week_start = today - timedelta(days=today.weekday())
month_start = today.replace(day=1)
today_total = counts.get(today.isoformat(), 0)
week_total = sum(count for day, count in counts.items() if week_start <= date.fromisoformat(day) <= today)
month_total = sum(count for day, count in counts.items() if month_start <= date.fromisoformat(day) <= today)
last_30_start = today - timedelta(days=29)
last_30_counts = [count for day, count in counts.items() if last_30_start <= date.fromisoformat(day) <= today]
last_30_total = sum(last_30_counts)
last_30_active_days = sum(count > 0 for count in last_30_counts)
last_30_peak = max(last_30_counts, default=0)
current = 0
cursor = today
while counts.get(cursor.isoformat(), 0) > 0:
    current += 1
    cursor -= timedelta(days=1)
longest = run = 0
for entry in days:
    run = run + 1 if entry["contributionCount"] > 0 else 0
    longest = max(longest, run)


def draw_streak(t):
    body = f'<circle cx="215" cy="143" r="65" fill="none" stroke="{t["purple"]}" stroke-width="9"/><text x="215" y="150" text-anchor="middle" fill="{t["cyan"]}" font-family="Fira Code, monospace" font-size="39" font-weight="700">{current}</text><text x="215" y="232" text-anchor="middle" fill="{t["muted"]}" font-family="Arial, sans-serif" font-size="13">CURRENT STREAK</text><path d="M350 80V210" stroke="{t["grid"]}"/><text x="510" y="145" text-anchor="middle" fill="{t["green"]}" font-family="Fira Code, monospace" font-size="50" font-weight="700">{longest}</text><text x="510" y="182" text-anchor="middle" fill="{t["muted"]}" font-family="Arial, sans-serif" font-size="13">LONGEST STREAK</text>'
    return card("contribution_streak --last-year", body, t)


def draw_pulse(t):
    metrics = [("TODAY", today_total, t["cyan"]), ("THIS WEEK", week_total, t["purple"]), ("THIS MONTH", month_total, t["green"])]
    body = f'<text x="32" y="73" fill="{t["muted"]}" font-family="Fira Code, monospace" font-size="12">IST calendar · updated twice daily</text>'
    for index, (label, value, color) in enumerate(metrics):
        x = 46 + index * 215
        body += f'<rect x="{x}" y="92" width="180" height="112" rx="12" fill="{t["panel"]}"/><text x="{x+90}" y="151" text-anchor="middle" fill="{color}" font-family="Fira Code, monospace" font-size="42" font-weight="700">{value}</text><text x="{x+90}" y="181" text-anchor="middle" fill="{t["muted"]}" font-family="Arial, sans-serif" font-size="12">{label}</text>'
    return card("contribution_pulse --IST", body, t)


def draw_momentum(t):
    metrics = [("ACTIVE DAYS", last_30_active_days, t["cyan"]), ("30D TOTAL", last_30_total, t["purple"]), ("PEAK DAY", last_30_peak, t["green"])]
    body = f'<text x="32" y="73" fill="{t["muted"]}" font-family="Fira Code, monospace" font-size="12">last 30 days · IST calendar</text>'
    for index, (label, value, color) in enumerate(metrics):
        x = 46 + index * 215
        body += f'<rect x="{x}" y="92" width="180" height="112" rx="12" fill="{t["panel"]}"/><text x="{x+90}" y="151" text-anchor="middle" fill="{color}" font-family="Fira Code, monospace" font-size="42" font-weight="700">{value}</text><text x="{x+90}" y="181" text-anchor="middle" fill="{t["muted"]}" font-family="Arial, sans-serif" font-size="12">{label}</text>'
    return card("momentum --30d", body, t)


def draw_activity(t):
    values = [entry["contributionCount"] for entry in days]
    maximum = max(values) or 1
    sampled = values[-90:]
    points = " ".join(f"{32+i*7:.1f},{207-(value/maximum)*125:.1f}" for i, value in enumerate(sampled))
    body = f'<line x1="32" y1="207" x2="670" y2="207" stroke="{t["grid"]}"/><polyline points="{points}" fill="none" stroke="{t["cyan"]}" stroke-width="3" stroke-linejoin="round"/><text x="32" y="235" fill="{t["muted"]}" font-family="Fira Code, monospace" font-size="12">last 90 days</text><text x="670" y="235" text-anchor="end" fill="{t["green"]}" font-family="Fira Code, monospace" font-size="12">peak: {maximum} contributions/day</text>'
    return card("activity_graph --contributions", body, t)


save("stats", draw_stats)
save("top-languages", draw_languages)
save("streak", draw_streak)
save("contribution-pulse", draw_pulse)
save("momentum", draw_momentum)
save("activity-graph", draw_activity)

# The interactive GitHub Pages dashboard reads the same contribution data as the cards.
(OUT / "contributions.json").write_text(
    json.dumps({"generated_at": now.isoformat(), "days": days}, separators=(",", ":")),
    encoding="utf-8",
)
