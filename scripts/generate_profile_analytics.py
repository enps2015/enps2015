#!/usr/bin/env python3
"""Build a Portuguese GitHub analytics panel using the official REST API.

Only public repositories, repository language aggregates, and public events are used.
The generated SVG is refreshed by GitHub Actions; this is a daily snapshot, not live telemetry.
"""
from __future__ import annotations

import html
import json
import os
import time
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER = "enps2015"
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "profile" / "metrics-overview.svg"
TOKEN = os.environ.get("GITHUB_TOKEN", "")

BG = "#081321"
PANEL = "#102337"
PANEL_ALT = "#14273A"
BORDER = "#29475C"
TEXT = "#F2F7FB"
MUTED = "#9FB6C6"
CYAN = "#67E8F9"
TEAL = "#2DD4BF"
VIOLET = "#A78BFA"
BLUE = "#7CB7FF"


def api_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "enps2015-profile-analytics",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_owned_repositories() -> list[dict]:
    results: list[dict] = []
    for page in range(1, 11):
        url = f"{API}/users/{USER}/repos?type=owner&sort=updated&per_page=100&page={page}"
        batch = api_json(url)
        if not isinstance(batch, list) or not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
    # Forked repositories inflate language and popularity totals for the account owner.
    return [repo for repo in results if not repo.get("fork", False)]


def fetch_language_totals(repositories: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for index, repo in enumerate(repositories, start=1):
        url = repo.get("languages_url")
        if not url:
            continue
        try:
            languages = api_json(url)
            if isinstance(languages, dict):
                for name, count in languages.items():
                    totals[name] = totals.get(name, 0) + int(count)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            # A single repository's language endpoint must not blank the entire dashboard.
            continue
        # Stay well below secondary-rate-limit thresholds.
        if index % 20 == 0:
            time.sleep(0.2)
    return totals


def fetch_recent_public_events() -> list[dict]:
    events: list[dict] = []
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=12)
    # The public events endpoint returns at most 300 recent events across 3 pages.
    for page in range(1, 4):
        try:
            batch = api_json(f"{API}/users/{USER}/events/public?per_page=100&page={page}")
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            break
        if not isinstance(batch, list) or not batch:
            break
        stop = False
        for event in batch:
            try:
                created = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            except (KeyError, ValueError, TypeError):
                continue
            if created >= cutoff:
                events.append(event)
            else:
                stop = True
                break
        if stop or len(batch) < 100:
            break
    return events


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_svg(repositories: list[dict], languages: dict[str, int], events: list[dict]) -> str:
    repo_count = len(repositories)
    stars = sum(int(r.get("stargazers_count", 0) or 0) for r in repositories)
    forks = sum(int(r.get("forks_count", 0) or 0) for r in repositories)
    lang_names = len(languages)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%d/%m/%Y · %H:%M UTC")

    # Aggregate the sampled public event feed into the last 12 Monday-to-Sunday periods.
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    first_monday = monday - timedelta(weeks=11)
    weeks = [first_monday + timedelta(weeks=i) for i in range(12)]
    counts = [0] * 12
    for event in events:
        try:
            created = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).date()
        except (KeyError, ValueError, TypeError):
            continue
        event_monday = created - timedelta(days=created.weekday())
        slot = (event_monday - first_monday).days // 7
        if 0 <= slot < len(counts):
            counts[slot] += 1

    language_items = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:5]
    total_bytes = sum(max(0, count) for count in languages.values()) or 1
    max_events = max(counts) or 1

    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="470" viewBox="0 0 1280 470" role="img" aria-labelledby="title desc">',
        '<title id="title">Painel analítico do GitHub de Eric Pimentel</title>',
        '<desc id="desc">Repositórios próprios públicos, estrelas, forks, linguagens detectadas e amostra de eventos públicos nas últimas doze semanas, consultados na API oficial do GitHub.</desc>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#071321"/><stop offset="1" stop-color="#17162E"/></linearGradient><linearGradient id="line" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#2DD4BF"/><stop offset=".55" stop-color="#67E8F9"/><stop offset="1" stop-color="#A78BFA"/></linearGradient></defs>',
        '<rect width="1280" height="470" rx="22" fill="url(#bg)"/>',
        '<rect x=".5" y=".5" width="1279" height="469" rx="21.5" fill="none" stroke="#29475C"/>',
        f'<text x="34" y="37" fill="{CYAN}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="11" font-weight="700" letter-spacing="2.5">GITHUB · PAINEL DE SINAIS PÚBLICOS</text>',
        f'<text x="34" y="63" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="23" font-weight="800">Projetos, linguagens e atividade recente</text>',
        f'<text x="1246" y="37" text-anchor="end" fill="{MUTED}" font-family="ui-monospace,Consolas,monospace" font-size="10">ATUALIZADO EM {esc(stamp)}</text>',
        f'<text x="1246" y="63" text-anchor="end" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="11">Fonte: API pública do GitHub</text>',
    ]

    cards = [
        (34, "REPOSITÓRIOS PRÓPRIOS", f"{repo_count}", TEAL),
        (340, "ESTRELAS RECEBIDAS", f"{stars}", CYAN),
        (646, "FORKS DOS PROJETOS", f"{forks}", BLUE),
        (952, "LINGUAGENS DETECTADAS", f"{lang_names}", VIOLET),
    ]
    for x, label, value, color in cards:
        chunks.extend([
            f'<rect x="{x}" y="83" width="294" height="88" rx="13" fill="{PANEL}" stroke="{BORDER}"/>',
            f'<rect x="{x+16}" y="100" width="4" height="48" rx="2" fill="{color}"/>',
            f'<text x="{x+32}" y="108" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10" font-weight="700" letter-spacing="1.1">{esc(label)}</text>',
            f'<text x="{x+32}" y="145" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="30" font-weight="800">{esc(value)}</text>',
        ])

    # Activity panel: 12 weeks of the latest public events visible via GitHub's API.
    chunks.extend([
        f'<rect x="34" y="190" width="742" height="224" rx="14" fill="{PANEL}" stroke="{BORDER}"/>',
        f'<text x="56" y="218" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="14" font-weight="800">Eventos públicos · últimas 12 semanas</text>',
        f'<text x="56" y="237" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10.5">Volume de eventos recentes retornados pelo feed público</text>',
    ])
    chart_x, chart_y, chart_w, chart_h = 57, 257, 694, 111
    chunks.append(f'<path d="M{chart_x} {chart_y+chart_h}H{chart_x+chart_w}" stroke="{BORDER}" stroke-width="1"/>')
    step = chart_w / 12
    bar_w = 25
    for i, (week, count) in enumerate(zip(weeks, counts)):
        height = int((count / max_events) * (chart_h - 16)) if count else 2
        x = chart_x + i * step + (step - bar_w) / 2
        y = chart_y + chart_h - height
        opacity = 0.55 + (0.4 * count / max_events) if count else 0.20
        chunks.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{height}" rx="4" fill="url(#line)" opacity="{opacity:.2f}"/>')
        chunks.append(f'<text x="{x+bar_w/2:.1f}" y="{chart_y+chart_h+17}" text-anchor="middle" fill="{MUTED}" font-family="ui-monospace,Consolas,monospace" font-size="9">{week.strftime("%d/%m")}</text>')
        if count:
            chunks.append(f'<text x="{x+bar_w/2:.1f}" y="{max(chart_y+10,y-6):.1f}" text-anchor="middle" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="9">{count}</text>')
    chunks.append(f'<text x="56" y="397" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="9.5">Amostra limitada aos eventos públicos recentes que a API disponibiliza (até 300 eventos).</text>')

    # Language panel: repository language bytes, not a skill rating.
    chunks.extend([
        f'<rect x="798" y="190" width="448" height="224" rx="14" fill="{PANEL}" stroke="{BORDER}"/>',
        f'<text x="820" y="218" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="14" font-weight="800">Composição do código público</text>',
        f'<text x="820" y="237" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10.5">Por volume de bytes detectado nos repositórios próprios</text>',
    ])
    if language_items:
        for i, (name, count) in enumerate(language_items):
            y = 265 + i * 27
            percent = max(0, count) / total_bytes * 100
            width = 250 * percent / max((max(c for _, c in languages.items()) / total_bytes * 100), 1)
            color = [CYAN, TEAL, BLUE, VIOLET, "#F4B860"][i % 5]
            chunks.extend([
                f'<text x="820" y="{y}" fill="{TEXT}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="11">{esc(name)}</text>',
                f'<rect x="930" y="{y-9}" width="190" height="9" rx="4.5" fill="{PANEL_ALT}"/>',
                f'<rect x="930" y="{y-9}" width="{190*percent/100:.2f}" height="9" rx="4.5" fill="{color}"/>',
                f'<text x="1220" y="{y}" text-anchor="end" fill="{MUTED}" font-family="ui-monospace,Consolas,monospace" font-size="10">{percent:.1f}%</text>',
            ])
    else:
        chunks.append(f'<text x="820" y="278" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="12">Não foi possível recuperar os dados de linguagens nesta execução.</text>')

    chunks.extend([
        f'<path d="M34 435H1246" stroke="{BORDER}"/>',
        f'<text x="34" y="453" fill="{MUTED}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="10">Indicadores de atividade pública; não representam proficiência, certificações ou impacto dos projetos.</text>',
        f'<text x="1246" y="453" text-anchor="end" fill="{CYAN}" font-family="ui-monospace,Consolas,monospace" font-size="10">GERADO AUTOMATICAMENTE · GITHUB ACTIONS</text>',
        '</svg>',
    ])
    return "\n".join(chunks)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    repositories = fetch_owned_repositories()
    languages = fetch_language_totals(repositories)
    events = fetch_recent_public_events()
    OUTPUT.write_text(render_svg(repositories, languages, events), encoding="utf-8")
    print(
        f"Gerado {OUTPUT.name}: {len(repositories)} repositórios próprios, "
        f"{len(languages)} linguagens, {len(events)} eventos públicos recentes."
    )


if __name__ == "__main__":
    main()
