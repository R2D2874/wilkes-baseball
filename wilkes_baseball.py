#!/usr/bin/env python3
"""
Wilkes Colonels Baseball 2026 Season Dashboard
Custom site for tracking the season with a focus on Ryan Campbell.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import re
import html as html_lib

BASE_URL = "https://gowilkesu.com"
SCHEDULE_URL = f"{BASE_URL}/sports/baseball/schedule/2026"
STATS_URL = f"{BASE_URL}/sports/baseball/stats?path=baseball"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

HEADERS = {"User-Agent": "WilkesBaseballDashboard/1.0"}

PLAYER_NAME = "Campbell"
PLAYER_FIRST = "Ryan"
PLAYER_FULL = "Ryan Campbell"
PLAYER_NUMBER = "24"
PLAYER_POSITION = "OF"
PLAYER_CLASS = "Sophomore"
PLAYER_BATS_THROWS = "R/R"
PLAYER_HOMETOWN = "Wilmington, DE"
PLAYER_HIGH_SCHOOL = "Archmere Academy"
PLAYER_MAJOR = "Sports Management"
PLAYER_HEADSHOT = "https://gowilkesu.com/images/2026/2/10/Campbell.png"

PLAYER_BIO = (
    "Ryan Campbell is a sophomore outfielder for the Wilkes University Colonels. "
    "A native of Wilmington, Delaware, Ryan attended Archmere Academy where he was "
    "a standout on the diamond. He is currently majoring in Sports Management at Wilkes. "
    "Ryan wears #24 and bats and throws right-handed."
)


def fetch_page(url):
    """Fetch a page and return BeautifulSoup object."""
    print(f"  Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ---------------------------------------------------------------------------
# Schedule parsing
# ---------------------------------------------------------------------------

def parse_schedule():
    """Parse the 2026 schedule for game results and box score links."""
    soup = fetch_page(SCHEDULE_URL)
    games = []
    wins = 0
    losses = 0

    game_rows = soup.select(".sidearm-schedule-game")
    if not game_rows:
        game_rows = soup.select("[class*='schedule'] [class*='game']")

    for row in game_rows:
        game = {}

        # Date
        date_el = row.select_one(".sidearm-schedule-game-opponent-date, [class*='date']")
        if date_el:
            raw = date_el.get_text(strip=True)
            m = re.match(r"(\w+ \d+)\s*\(\w+\)\s*([\d:]+\s*[AP]M)?", raw)
            if m:
                game["date"] = m.group(1)
                game["time"] = m.group(2) or ""
            else:
                game["date"] = raw
                game["time"] = ""

        # Opponent
        opp_el = row.select_one(".sidearm-schedule-game-opponent-name a, .sidearm-schedule-game-opponent-name")
        if opp_el:
            opp_text = opp_el.get_text(" ", strip=True)
            opp_text = re.sub(r"(Box Score|Recap|Live Stats)", "", opp_text).strip()
            opp_text = re.sub(r"^\w+ \d+\s*\(\w+\)\s*[\d:]+\s*[AP]M\s*", "", opp_text)
            opp_text = re.sub(r"^(vs|at)\s+", "", opp_text, flags=re.I).strip()
            opp_text = re.sub(r"#\d+\s*", "", opp_text).strip()
            game["opponent"] = opp_text

        # Location (home/away)
        full_text = row.get_text()
        if "at" in full_text and "at" not in (game.get("opponent", "").lower()):
            game["location"] = "at"
        else:
            game["location"] = "vs"

        # Result
        result_el = row.select_one(".sidearm-schedule-game-result, [class*='result']")
        if result_el:
            result_text = result_el.get_text(strip=True)
            game["result_raw"] = result_text

            if result_text.startswith("W"):
                wins += 1
                game["outcome"] = "W"
            elif result_text.startswith("L"):
                losses += 1
                game["outcome"] = "L"
            else:
                game["outcome"] = ""

            score_match = re.search(r"(\d+)\s*-\s*(\d+)", result_text)
            if score_match:
                game["score"] = f"{score_match.group(1)}-{score_match.group(2)}"

        # Box score link
        box_link = row.select_one("a[href*='boxscore'], a[href*='box_score']")
        if box_link:
            href = box_link.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + href
            game["box_score_url"] = href

        if game.get("opponent"):
            games.append(game)

    return {"games": games, "wins": wins, "losses": losses}


# ---------------------------------------------------------------------------
# Team stats parsing (hitting only + Campbell fielding)
# ---------------------------------------------------------------------------

SKIP_TABLES = {
    "pitching", "pitch", "era", "innings pitched", "wins", "saves",
    "stolen bases against", "caught stealing by", "passed balls",
    "fielding double plays", "assists", "errors",
    "fielding percentage", "total chances", "putouts",
}

CAMPBELL_FIELDING_TABLES = {
    "Individual Overall Fielding Statistics",
}


def should_include_table(label):
    lower = label.lower()
    for skip in SKIP_TABLES:
        if skip in lower:
            return False
    return True


def parse_team_stats():
    """Parse team stats page. Returns (hitting_stats, campbell_overall, campbell_fielding, all_batting)."""
    soup = fetch_page(STATS_URL)
    tables = soup.select("table")

    team_hitting = {}
    campbell_overall = {}
    campbell_fielding = {}
    all_batting = None

    for table in tables:
        caption = table.select_one("caption")
        label = caption.get_text(strip=True) if caption else ""
        if not label:
            continue

        headers_row = table.select_one("thead tr")
        col_headers = []
        if headers_row:
            col_headers = [th.get_text(strip=True) for th in headers_row.select("th, td")]
            col_headers = [h for h in col_headers if h != "Bio Link"]

        rows = []
        for tr in table.select("tbody tr"):
            cells = [td.get_text(strip=True) for td in tr.select("td, th")]
            if cells and cells[-1] == "View Bio":
                cells = cells[:-1]
            is_campbell = any("campbell" in c.lower() for c in cells)

            if len(cells) > 1:
                cells[1] = re.sub(r"(\d+)(.+)", "", cells[1]).strip()
                name_match = re.match(r"^(.+?)\d+\1$", cells[1])
                if name_match:
                    cells[1] = name_match.group(1)

            if any(c for c in cells):
                rows.append({"cells": cells, "highlight": is_campbell})

        if not rows:
            continue

        if label == "Individual Overall Batting Statistics":
            all_batting = {"headers": col_headers, "rows": rows}
            campbell_rows = [r for r in rows if r["highlight"]]
            if campbell_rows:
                campbell_overall["hitting"] = {
                    "headers": col_headers,
                    "row": campbell_rows[0]["cells"],
                }

        if label in CAMPBELL_FIELDING_TABLES:
            campbell_rows = [r for r in rows if r["highlight"]]
            if campbell_rows:
                campbell_fielding = {
                    "headers": col_headers,
                    "row": campbell_rows[0]["cells"],
                }

        if should_include_table(label):
            team_hitting[label] = {"headers": col_headers, "rows": rows}

    return team_hitting, campbell_overall, campbell_fielding, all_batting


def find_campbell_team_leads(team_hitting, all_batting=None):
    """Determine which stats Campbell leads the team in."""
    table = all_batting or team_hitting.get("Individual Overall Batting Statistics")
    if not table:
        return set()

    hdrs = table["headers"]
    rows = table["rows"]

    check_stats = {"AVG", "OPS", "H", "R", "RBI", "2B", "3B", "HR", "BB", "SB-ATT",
                   "SLG%", "OB%", "AB"}

    campbell_row = None
    all_rows = []
    for r in rows:
        cells = r["cells"]
        name = cells[1] if len(cells) > 1 else ""
        if "total" in name.lower() or "opponent" in name.lower():
            continue
        all_rows.append(cells)
        if r["highlight"]:
            campbell_row = cells

    if not campbell_row:
        return set()

    leads = set()
    for stat in check_stats:
        if stat not in hdrs:
            continue
        idx = hdrs.index(stat)

        campbell_val = campbell_row[idx] if idx < len(campbell_row) else ""
        try:
            c_num = float(campbell_val)
        except (ValueError, TypeError):
            continue

        is_leader = True
        for row in all_rows:
            if row is campbell_row:
                continue
            other_val = row[idx] if idx < len(row) else ""
            try:
                o_num = float(other_val)
            except (ValueError, TypeError):
                continue
            if o_num > c_num:
                is_leader = False
                break

        if is_leader:
            leads.add(stat)

    return leads


# ---------------------------------------------------------------------------
# Box score parsing - Campbell's per-game stats + plays
# ---------------------------------------------------------------------------

def parse_box_score(url, opponent, date):
    """Parse a box score page for Campbell's line and plays."""
    try:
        soup = fetch_page(url)
    except Exception as e:
        print(f"    Warning: {e}")
        return None

    result = {"opponent": opponent, "date": date, "url": url}

    tables = soup.select("table")

    for table in tables:
        caption = table.select_one("caption")
        label = (caption.get_text(strip=True) if caption else "").lower()

        if "score by innings" in label or "team score" in label:
            rows = []
            for tr in table.select("tr"):
                cells = [td.get_text(strip=True) for td in tr.select("td, th")]
                rows.append(cells)
            result["linescore"] = rows

        if "wilkes" in label and "pitch" not in label:
            for tr in table.select("tbody tr"):
                if "campbell" in tr.get_text().lower():
                    cells = [td.get_text(strip=True) for td in tr.select("td, th")]
                    hdr_row = table.select_one("thead tr")
                    hdrs = []
                    if hdr_row:
                        hdrs = [th.get_text(strip=True) for th in hdr_row.select("th, td")]
                    if len(cells) > 1:
                        cells[1] = re.sub(r"\d+.*$", "", cells[1]).strip()
                        if not cells[1]:
                            cells[1] = "Campbell, Ryan"
                    result["batting"] = {"headers": hdrs, "cells": cells}
                    break

    # Campbell's play-by-play from inning tables
    plays = []
    seen_plays = set()
    for table in tables:
        caption = table.select_one("caption")
        label = caption.get_text(strip=True) if caption else ""
        if "wilkes" in label.lower() and ("top" in label.lower() or "bottom" in label.lower()):
            inning_match = re.search(r"(Top|Bottom) of (\w+)", label, re.I)
            inning = inning_match.group(2) if inning_match else ""

            for tr in table.select("tbody tr"):
                text = tr.get_text(strip=True)
                if "campbell" in text.lower() or "r. campbell" in text.lower():
                    cells = [td.get_text(strip=True) for td in tr.select("td, th")]
                    play_desc = cells[0] if cells else text
                    key = f"{inning}:{play_desc}"
                    if key not in seen_plays:
                        seen_plays.add(key)
                        plays.append({"inning": inning, "description": play_desc})

    result["plays"] = plays
    return result


def fetch_campbell_game_log(games):
    """Fetch box scores for all completed games and extract Campbell's stats."""
    game_log = []
    for g in games:
        if not g.get("box_score_url") or not g.get("outcome"):
            continue
        print(f"    Game: {g.get('date', '?')} vs {g.get('opponent', '?')}")
        data = parse_box_score(g["box_score_url"], g.get("opponent", ""), g.get("date", ""))
        if data:
            data["outcome"] = g.get("outcome", "")
            data["score"] = g.get("score", "")
            game_log.append(data)
    return game_log


# ---------------------------------------------------------------------------
# Photo scraping from Wilkes baseball page
# ---------------------------------------------------------------------------

def fetch_photos():
    """Try to grab player/team photos from the Wilkes baseball galleries."""
    photos = []
    # Always include the headshot
    photos.append(PLAYER_HEADSHOT)

    # Try roster page for additional headshots or team images
    try:
        soup = fetch_page(f"{BASE_URL}/sports/baseball/roster")
        for img in soup.select("img"):
            src = img.get("src", "") or img.get("data-src", "")
            if src and ("baseball" in src.lower() or "roster" in src.lower()):
                if not src.startswith("http"):
                    src = BASE_URL + src
                if src not in photos and len(photos) < 12:
                    photos.append(src)
    except Exception as e:
        print(f"  Warning fetching roster photos: {e}")

    return photos


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def esc(text):
    return html_lib.escape(str(text))


def generate_html(schedule, campbell_overall, campbell_fielding, campbell_game_log, team_hitting, campbell_leads=None, photos=None):
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    record = f"{schedule['wins']}-{schedule['losses']}"

    # --- Campbell season stats card ---
    campbell_hitting_html = ""
    if "hitting" in campbell_overall:
        h = campbell_overall["hitting"]
        hdrs = h["headers"]
        vals = h["row"]
        stat_map = {}
        for i, hdr in enumerate(hdrs):
            if i < len(vals):
                stat_map[hdr] = vals[i]

        key_stats = [
            ("AVG", stat_map.get("AVG", "-")),
            ("OPS", stat_map.get("OPS", "-")),
            ("H", stat_map.get("H", "-")),
            ("R", stat_map.get("R", "-")),
            ("RBI", stat_map.get("RBI", "-")),
            ("2B", stat_map.get("2B", "-")),
            ("3B", stat_map.get("3B", "-")),
            ("HR", stat_map.get("HR", "-")),
            ("BB", stat_map.get("BB", "-")),
            ("SB-ATT", stat_map.get("SB-ATT", "-")),
            ("SO", stat_map.get("SO", "-")),
            ("SLG%", stat_map.get("SLG%", "-")),
            ("OB%", stat_map.get("OB%", "-")),
            ("GP-GS", stat_map.get("GP-GS", "-")),
            ("AB", stat_map.get("AB", "-")),
        ]

        leads = campbell_leads or set()
        cards = ""
        for label, val in key_stats:
            big = label in ("AVG", "OPS", "H", "RBI", "R")
            is_leader = label in leads
            classes = "stat-big" if big else "stat-small"
            if is_leader:
                classes += " team-leader"
            badge = '<span class="team-leader-badge">Team Leader</span>' if is_leader else ""
            cards += f'<div class="stat-card {classes}">{badge}<div class="stat-val">{esc(val)}</div><div class="stat-label">{esc(label)}</div></div>\n'

        campbell_hitting_html = f'<div class="stat-grid">{cards}</div>'

    # Campbell fielding
    campbell_fielding_html = ""
    if campbell_fielding:
        h = campbell_fielding
        stat_map = {}
        for i, hdr in enumerate(h["headers"]):
            if i < len(h["row"]):
                stat_map[hdr] = h["row"][i]
        fielding_stats = [
            ("FLD%", stat_map.get("FLD%", "-")),
            ("PO", stat_map.get("PO", "-")),
            ("A", stat_map.get("A", "-")),
            ("E", stat_map.get("E", "-")),
            ("C", stat_map.get("C", "-")),
        ]
        cards = ""
        for label, val in fielding_stats:
            cards += f'<div class="stat-card stat-small"><div class="stat-val">{esc(val)}</div><div class="stat-label">{esc(label)}</div></div>\n'
        campbell_fielding_html = f'''
        <h3 class="sub-heading">Fielding</h3>
        <div class="stat-grid">{cards}</div>'''

    # --- Campbell game log ---
    game_log_rows = ""
    if campbell_game_log:
        batting_hdrs = []
        for g in campbell_game_log:
            if g.get("batting"):
                batting_hdrs = g["batting"]["headers"]
                break

        keep_cols = ["AB", "R", "H", "RBI", "BB", "SO", "SB", "CS", "HBP", "2B", "3B", "HR"]
        col_indices = []
        display_hdrs = []
        for col in keep_cols:
            for i, h in enumerate(batting_hdrs):
                if h == col:
                    col_indices.append(i)
                    display_hdrs.append(col)
                    break

        for g in campbell_game_log:
            outcome_class = "w" if g.get("outcome") == "W" else "l"
            plays_html = ""
            if g.get("plays"):
                play_items = ""
                for p in g["plays"]:
                    play_items += f'<div class="play"><span class="inning-tag">{esc(p["inning"])}</span> {esc(p["description"])}</div>\n'
                plays_html = f'<div class="plays-wrap">{play_items}</div>'

            stat_cells = ""
            if g.get("batting"):
                cells = g["batting"]["cells"]
                for idx in col_indices:
                    val = cells[idx] if idx < len(cells) else "-"
                    stat_cells += f"<td>{esc(val)}</td>"
            else:
                stat_cells = f'<td colspan="{len(display_hdrs)}">-</td>'

            game_log_rows += f'''
            <tr class="game-row {outcome_class}" onclick="this.classList.toggle('expanded')">
                <td class="gl-date">{esc(g.get("date", ""))}</td>
                <td class="gl-opp">{esc(g.get("opponent", ""))}</td>
                <td class="gl-result"><span class="badge-{outcome_class}">{esc(g.get("outcome", ""))}</span> {esc(g.get("score", ""))}</td>
                {stat_cells}
            </tr>
            <tr class="plays-row {outcome_class}">
                <td colspan="{3 + len(display_hdrs)}">
                    {plays_html if plays_html else '<div class="plays-wrap"><em>No play-by-play available</em></div>'}
                </td>
            </tr>'''

        hdr_cells = "".join(f"<th>{esc(h)}</th>" for h in display_hdrs)
        game_log_html = f'''
        <table class="game-log">
            <thead><tr><th>Date</th><th>Opponent</th><th>Result</th>{hdr_cells}</tr></thead>
            <tbody>{game_log_rows}</tbody>
        </table>'''
    else:
        game_log_html = '<p class="empty">No game data available yet.</p>'

    # --- Photos ---
    photo_list = photos or [PLAYER_HEADSHOT]
    photo_grid_items = ""
    for p in photo_list:
        photo_grid_items += f'            <img src="{esc(p)}" alt="Ryan Campbell - Wilkes Baseball">\n'

    # --- Schedule ---
    schedule_rows = ""
    for g in schedule["games"]:
        outcome = g.get("outcome", "")
        if outcome:
            outcome_class = "w" if outcome == "W" else "l"
            badge = f'<span class="badge-{outcome_class}">{outcome}</span> {esc(g.get("score", ""))}'
        else:
            badge = '<span class="badge-upcoming">Upcoming</span>'

        box_link = ""
        if g.get("box_score_url"):
            box_link = f'<a href="{esc(g["box_score_url"])}" target="_blank" class="box-link">Box Score</a>'

        loc = g.get("location", "vs")
        schedule_rows += f'''
        <tr>
            <td class="sched-date">{esc(g.get("date", "TBD"))}</td>
            <td class="sched-opp">{esc(loc)} {esc(g.get("opponent", "Unknown"))}</td>
            <td class="sched-result">{badge}</td>
            <td class="sched-box">{box_link}</td>
        </tr>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ryan / Wilkes Baseball Colonels Baseball</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        :root {{
            --navy: #104076;
            --navy-dark: #0A2A52;
            --navy-light: #1A5CAA;
            --gold: #FCD213;
            --gold-light: #FDE566;
            --bg: #0B0E14;
            --surface: #141924;
            --surface-2: #1C2333;
            --surface-3: #243044;
            --border: #2A3548;
            --text: #E8ECF2;
            --text-muted: #7A8BA8;
            --green: #34D399;
            --green-bg: rgba(52, 211, 153, 0.1);
            --red: #F87171;
            --red-bg: rgba(248, 113, 113, 0.1);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        /* --- Hero --- */
        .hero {{
            background: linear-gradient(160deg, var(--navy-dark) 0%, var(--navy) 40%, var(--navy-light) 100%);
            padding: 3rem 2rem 2.5rem;
            position: relative;
            overflow: hidden;
        }}
        .hero::after {{
            content: '';
            position: absolute;
            top: -50%;
            right: -20%;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(252,210,19,0.12) 0%, transparent 70%);
            pointer-events: none;
        }}
        .hero-inner {{
            max-width: 1000px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }}
        .hero-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}
        .hero h1 {{
            font-size: 1.6rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: white;
        }}
        .hero .subtitle {{
            font-size: 0.85rem;
            color: rgba(255,255,255,0.6);
            margin-top: 0.15rem;
        }}
        .record-block {{
            text-align: right;
        }}
        .record-num {{
            font-size: 2.8rem;
            font-weight: 900;
            color: var(--gold);
            line-height: 1;
            letter-spacing: -0.03em;
        }}
        .record-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: rgba(255,255,255,0.5);
        }}
        .updated {{
            font-size: 0.7rem;
            color: rgba(255,255,255,0.35);
            margin-top: 1rem;
        }}

        /* --- Player Card in Hero --- */
        .player-card {{
            display: flex;
            gap: 1.5rem;
            align-items: center;
            margin-top: 1.5rem;
            background: rgba(0,0,0,0.25);
            border-radius: 12px;
            padding: 1.25rem;
            border: 1px solid rgba(252,210,19,0.15);
        }}
        .player-card img {{
            width: 120px;
            height: 150px;
            object-fit: cover;
            border-radius: 8px;
            border: 2px solid rgba(252,210,19,0.3);
        }}
        .player-info {{
            flex: 1;
        }}
        .player-info .player-name {{
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--gold);
        }}
        .player-info .player-details {{
            font-size: 0.8rem;
            color: rgba(255,255,255,0.7);
            margin-top: 0.3rem;
            line-height: 1.6;
        }}
        .player-info .player-bio {{
            font-size: 0.78rem;
            color: rgba(255,255,255,0.55);
            margin-top: 0.6rem;
            line-height: 1.6;
        }}

        /* --- Nav --- */
        .nav {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .nav-inner {{
            max-width: 1000px;
            margin: 0 auto;
            display: flex;
            gap: 0;
        }}
        .nav a {{
            padding: 0.85rem 1.25rem;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }}
        .nav a:hover, .nav a.active {{
            color: var(--gold);
            border-bottom-color: var(--gold);
        }}

        /* --- Container --- */
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }}

        /* --- Section --- */
        .section {{
            padding: 2rem 0;
        }}
        .section + .section {{
            border-top: 1px solid var(--border);
        }}
        .section-title {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 1.25rem;
            color: var(--text);
            letter-spacing: -0.01em;
        }}
        .sub-heading {{
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin: 1.5rem 0 0.75rem;
        }}

        /* --- Stat grid --- */
        .stat-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
        }}
        .stat-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            text-align: center;
            min-width: 72px;
            position: relative;
        }}
        .stat-card.team-leader {{
            border-color: var(--gold);
            box-shadow: 0 0 12px rgba(252, 210, 19, 0.15);
        }}
        .team-leader-badge {{
            position: absolute;
            top: -6px;
            right: -6px;
            background: linear-gradient(135deg, var(--gold) 0%, #C4A00E 100%);
            color: #1a1a22;
            font-size: 0.4rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 1px 4px;
            border-radius: 3px;
            line-height: 1.3;
            white-space: nowrap;
            box-shadow: 0 1px 4px rgba(252, 210, 19, 0.4);
        }}
        .stat-big {{
            background: var(--surface-2);
            border-color: var(--navy);
        }}
        .stat-big .stat-val {{
            font-size: 1.5rem;
            color: var(--gold);
        }}
        .stat-val {{
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.2;
        }}
        .stat-label {{
            font-size: 0.65rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.15rem;
        }}

        /* --- Tables --- */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
        }}
        thead th {{
            background: var(--surface-2);
            color: var(--text-muted);
            padding: 0.5rem 0.65rem;
            text-align: left;
            font-weight: 600;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            white-space: nowrap;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 0.55rem 0.65rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}
        tbody tr:hover {{
            background: var(--surface);
        }}

        /* --- Schedule table --- */
        .sched-date {{
            color: var(--text-muted);
            font-size: 0.78rem;
            width: 80px;
        }}
        .sched-opp {{
            font-weight: 600;
        }}
        .sched-result {{
            width: 120px;
        }}
        .sched-box {{
            width: 80px;
            text-align: right;
        }}
        .box-link {{
            color: var(--navy-light);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.78rem;
            padding: 0.25rem 0.5rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            transition: all 0.15s;
        }}
        .box-link:hover {{
            background: var(--navy);
            color: white;
            border-color: var(--navy);
        }}

        /* --- Badges --- */
        .badge-w {{
            display: inline-block;
            background: var(--green-bg);
            color: var(--green);
            font-weight: 700;
            font-size: 0.7rem;
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
            margin-right: 0.3rem;
        }}
        .badge-l {{
            display: inline-block;
            background: var(--red-bg);
            color: var(--red);
            font-weight: 700;
            font-size: 0.7rem;
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
            margin-right: 0.3rem;
        }}
        .badge-upcoming {{
            display: inline-block;
            background: var(--surface-2);
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.7rem;
            padding: 0.15rem 0.4rem;
            border-radius: 3px;
        }}

        /* --- Game log --- */
        .game-log {{ border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
        .game-log thead th {{ background: var(--surface-3); }}
        .game-row {{ cursor: pointer; transition: background 0.15s; }}
        .game-row:hover {{ background: var(--surface-2); }}
        .game-row.w {{ border-left: 3px solid var(--green); }}
        .game-row.l {{ border-left: 3px solid var(--red); }}
        .gl-date {{ color: var(--text-muted); font-size: 0.78rem; }}
        .gl-opp {{ font-weight: 600; }}

        .plays-row {{
            display: none;
        }}
        .game-row.expanded + .plays-row {{
            display: table-row;
        }}
        .plays-wrap {{
            padding: 0.5rem 0.25rem;
        }}
        .play {{
            padding: 0.3rem 0;
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.5;
        }}
        .inning-tag {{
            display: inline-block;
            background: var(--surface-3);
            color: var(--text-muted);
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.1rem 0.35rem;
            border-radius: 3px;
            margin-right: 0.35rem;
            min-width: 28px;
            text-align: center;
        }}

        /* --- Campbell highlight in team tables --- */
        tr.campbell td {{
            background: rgba(16, 64, 118, 0.15);
            color: var(--gold);
            font-weight: 600;
        }}

        .empty {{
            color: var(--text-muted);
            padding: 2rem;
            text-align: center;
        }}

        /* --- Photo Gallery --- */
        .photo-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
        }}
        .photo-grid img {{
            width: 100%;
            object-fit: contain;
            background: var(--surface);
            border-radius: 6px;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.2s;
        }}
        .photo-grid img:hover {{ opacity: 0.85; transform: scale(1.01); }}

        /* Lightbox */
        .lightbox {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.92);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        .lightbox.open {{ display: flex; }}
        .lightbox img {{
            max-width: 90vw;
            max-height: 90vh;
            object-fit: contain;
            border-radius: 4px;
        }}
        .lightbox-close {{
            position: absolute;
            top: 1rem;
            right: 1.25rem;
            color: white;
            font-size: 2rem;
            cursor: pointer;
            background: none;
            border: none;
            line-height: 1;
        }}

        @media (max-width: 700px) {{
            .hero {{ padding: 2rem 1.25rem 1.5rem; }}
            .hero h1 {{ font-size: 1.2rem; }}
            .record-num {{ font-size: 2rem; }}
            .player-card {{ flex-direction: column; text-align: center; }}
            .player-card img {{ width: 100px; height: 125px; }}
            .stat-card {{ min-width: 60px; padding: 0.5rem 0.6rem; }}
            .stat-big .stat-val {{ font-size: 1.2rem; }}
            .stat-grid {{ gap: 0.75rem; }}
            .team-leader-badge {{ font-size: 0.35rem; padding: 1px 3px; top: -5px; right: -5px; }}
            table {{ font-size: 0.75rem; }}
            td, th {{ padding: 0.4rem 0.45rem; }}
            .nav a {{ padding: 0.7rem 0.8rem; font-size: 0.7rem; }}
            .photo-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .photo-grid img:first-child {{ grid-column: span 2; }}
        }}
    </style>
</head>
<body>

<div class="hero">
    <div class="hero-inner">
        <div class="hero-top">
            <div>
                <h1>Ryan / Wilkes Baseball Colonels Baseball</h1>
                <div class="subtitle">2026 Season</div>
            </div>
            <div class="record-block">
                <div class="record-num">{esc(record)}</div>
                <div class="record-label">Record</div>
            </div>
        </div>
        <div class="player-card">
            <img src="{esc(PLAYER_HEADSHOT)}" alt="Ryan Campbell - Wilkes Colonels">
            <div class="player-info">
                <div class="player-name">#{esc(PLAYER_NUMBER)} {esc(PLAYER_FULL)}</div>
                <div class="player-details">
                    {esc(PLAYER_POSITION)} &bull; {esc(PLAYER_CLASS)} &bull; {esc(PLAYER_BATS_THROWS)}<br>
                    {esc(PLAYER_HOMETOWN)} / {esc(PLAYER_HIGH_SCHOOL)}<br>
                    Major: {esc(PLAYER_MAJOR)}
                </div>
                <div class="player-bio">{esc(PLAYER_BIO)}</div>
            </div>
        </div>
        <div class="updated">Updated {esc(now)}</div>
    </div>
</div>

<div class="nav">
    <div class="nav-inner">
        <a href="#campbell" class="active">Campbell</a>
        <a href="#photos">Photos</a>
        <a href="#schedule">Schedule</a>
    </div>
</div>

<div class="container">
    <!-- Campbell Section -->
    <div class="section" id="campbell">
        <div class="section-title">#{esc(PLAYER_NUMBER)} {esc(PLAYER_FULL)}</div>

        <h3 class="sub-heading">2026 Season Hitting</h3>
        {campbell_hitting_html if campbell_hitting_html else '<p class="empty">No hitting stats available yet.</p>'}

        {campbell_fielding_html}

        <h3 class="sub-heading"><strong style="color: var(--text); font-weight: 800;">Ryan\'s</strong> GAME LOG <span style="font-weight:400; color: var(--text-muted); font-size: 0.75rem; text-transform: none; letter-spacing: 0;">(click a game for play-by-play)</span></h3>
        {game_log_html}
    </div>

    <!-- Photos Section -->
    <div class="section" id="photos">
        <div class="section-title">Photos</div>
        <div class="photo-grid" id="photoGrid">
{photo_grid_items}
        </div>
    </div>

    <div class="lightbox" id="lightbox">
        <button class="lightbox-close" id="lightboxClose">&times;</button>
        <img id="lightboxImg" src="" alt="">
    </div>

    <!-- Schedule Section -->
    <div class="section" id="schedule">
        <div class="section-title">2026 Schedule</div>
        <div style="overflow-x: auto;">
            <table>
                <thead><tr><th>Date</th><th>Opponent</th><th>Result</th><th></th></tr></thead>
                <tbody>{schedule_rows}</tbody>
            </table>
        </div>
    </div>
</div>


<script>
// Photo lightbox
(function() {{
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImg');
    document.getElementById('photoGrid').querySelectorAll('img').forEach(img => {{
        img.addEventListener('click', () => {{
            lightboxImg.src = img.src;
            lightbox.classList.add('open');
        }});
    }});
    document.getElementById('lightboxClose').addEventListener('click', () => lightbox.classList.remove('open'));
    lightbox.addEventListener('click', e => {{ if (e.target === lightbox) lightbox.classList.remove('open'); }});
}})();

// Smooth scroll for nav
document.querySelectorAll('.nav a').forEach(a => {{
    a.addEventListener('click', e => {{
        const href = a.getAttribute('href');
        if (href.startsWith('#')) {{
            e.preventDefault();
            document.querySelector(href).scrollIntoView({{ behavior: 'smooth' }});
            document.querySelectorAll('.nav a').forEach(n => n.classList.remove('active'));
            a.classList.add('active');
        }}
    }});
}});

// Update active nav on scroll
const sections = document.querySelectorAll('.section[id]');
const navLinks = document.querySelectorAll('.nav a');
window.addEventListener('scroll', () => {{
    let current = '';
    sections.forEach(s => {{
        if (window.scrollY >= s.offsetTop - 100) current = s.id;
    }});
    navLinks.forEach(a => {{
        a.classList.toggle('active', a.getAttribute('href') === '#' + current);
    }});
}});
</script>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Wilkes Colonels Baseball 2026 Dashboard")
    print("=" * 45)

    print("\n[1/5] Fetching schedule...")
    try:
        schedule = parse_schedule()
        print(f"  Found {len(schedule['games'])} games | Record: {schedule['wins']}-{schedule['losses']}")
    except Exception as e:
        print(f"  Error: {e}")
        schedule = {"games": [], "wins": 0, "losses": 0}

    print("\n[2/5] Fetching team stats...")
    try:
        team_hitting, campbell_overall, campbell_fielding, all_batting = parse_team_stats()
        print(f"  Hitting tables: {len(team_hitting)}")
        print(f"  Campbell hitting: {'Yes' if 'hitting' in campbell_overall else 'No'}")
        print(f"  Campbell fielding: {'Yes' if campbell_fielding else 'No'}")
    except Exception as e:
        print(f"  Error: {e}")
        team_hitting, campbell_overall, campbell_fielding, all_batting = {}, {}, {}, None

    print("\n[3/5] Fetching box scores for Campbell game log...")
    try:
        campbell_game_log = fetch_campbell_game_log(schedule["games"])
        print(f"  Parsed {len(campbell_game_log)} box scores")
    except Exception as e:
        print(f"  Error: {e}")
        campbell_game_log = []

    print("\n[4/5] Fetching photos...")
    try:
        photos = fetch_photos()
        print(f"  Found {len(photos)} photos")
    except Exception as e:
        print(f"  Error: {e}")
        photos = [PLAYER_HEADSHOT]

    print("\n[5/5] Generating HTML...")
    campbell_leads = find_campbell_team_leads(team_hitting, all_batting)
    if campbell_leads:
        print(f"  Campbell leads team in: {', '.join(sorted(campbell_leads))}")
    html = generate_html(schedule, campbell_overall, campbell_fielding, campbell_game_log, team_hitting, campbell_leads, photos)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDashboard saved to: {OUTPUT_FILE}")
    print("Open it in your browser to view.")


if __name__ == "__main__":
    main()
