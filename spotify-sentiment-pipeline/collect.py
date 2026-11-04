import argparse
import csv
import json
import sqlite3
import time
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google_play_scraper import Sort, reviews as play_reviews

APPLE_ID = "324684580"
PLAY_ID = "com.spotify.music"
OUT = Path(__file__).parent / "data"
DB = OUT / "spotify_reviews.db"

FIELDS = [
    "review_id", "source", "company", "product", "rating", "review_title",
    "review_text", "review_date", "app_version", "developer_reply",
    "developer_reply_date", "thumbs_up",
]

FULL_CHUNK = 4500
UPDATE_CHUNK = 500


def retry(fn, attempts=4, wait=2):
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if i == attempts - 1:
                raise
            print(f"  request failed ({exc}), retrying in {wait * 2 ** i}s")
            time.sleep(wait * 2 ** i)


def apple_page(job):
    sort, page, country = job
    url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
           f"page={page}/id={APPLE_ID}/sortBy={sort}/json")
    try:
        data = retry(lambda: json.load(urllib.request.urlopen(url, timeout=30)), attempts=3)
    except Exception as exc:
        print(f"apple {sort} page {page}: skipped ({exc})")
        return []
    entries = data.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    return [e for e in entries if "im:rating" in e]


def fetch_apple(country="us"):
    jobs = [(sort, page, country) for sort in ("mostRecent", "mostHelpful") for page in range(1, 11)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        pages = list(pool.map(apple_page, jobs))
    rows = {}
    for e in (e for page in pages for e in page):
        rid = "apple_" + e["id"]["label"]
        rows[rid] = {
            "review_id": rid,
            "source": "app_store",
            "company": "Spotify",
            "product": "Spotify iOS app",
            "rating": int(e["im:rating"]["label"]),
            "review_title": e["title"]["label"],
            "review_text": e["content"]["label"],
            "review_date": e["updated"]["label"],
            "app_version": e.get("im:version", {}).get("label"),
            "developer_reply": None,
            "developer_reply_date": None,
            "thumbs_up": int(e.get("im:voteSum", {}).get("label", 0) or 0),
        }
    print(f"app store: {len(rows):,} reviews")
    return list(rows.values())


def play_row(r):
    return {
        "review_id": "play_" + r["reviewId"],
        "source": "google_play",
        "company": "Spotify",
        "product": "Spotify Android app",
        "rating": r["score"],
        "review_title": None,
        "review_text": r["content"],
        "review_date": r["at"].isoformat(),
        "app_version": r.get("appVersion") or r.get("reviewCreatedVersion"),
        "developer_reply": r.get("replyContent"),
        "developer_reply_date": r["repliedAt"].isoformat() if r.get("repliedAt") else None,
        "thumbs_up": r.get("thumbsUpCount", 0),
    }


def fetch_play(limit, since):
    chunk = UPDATE_CHUNK if since else FULL_CHUNK
    rows, token = {}, None
    while len(rows) < limit:
        batch, token = retry(lambda: play_reviews(
            PLAY_ID, lang="en", country="us", sort=Sort.NEWEST,
            count=min(chunk, limit - len(rows)), continuation_token=token))
        for r in batch:
            row = play_row(r)
            rows[row["review_id"]] = row
        print(f"google play: {len(rows):,} reviews fetched")
        if not batch or token is None:
            break
        if since and min(r["at"] for r in batch) < since:
            break
    return list(rows.values())[:limit]


def open_db(full):
    OUT.mkdir(exist_ok=True)
    db = sqlite3.connect(DB)
    if full:
        db.execute("DROP TABLE IF EXISTS reviews")
    db.execute(
        "CREATE TABLE IF NOT EXISTS reviews (review_id TEXT PRIMARY KEY, source TEXT, "
        "company TEXT, product TEXT, rating INTEGER, review_title TEXT, review_text TEXT, "
        "review_date TEXT, app_version TEXT, developer_reply TEXT, developer_reply_date TEXT, "
        "thumbs_up INTEGER)"
    )
    return db


def run(play_count=5000, full=False):
    start = time.time()
    db = open_db(full)
    known = {r[0] for r in db.execute("SELECT review_id FROM reviews WHERE source = 'google_play'")}
    latest = db.execute("SELECT MAX(review_date) FROM reviews WHERE source = 'google_play'").fetchone()[0]
    since = datetime.fromisoformat(latest) if latest else None
    print(f"updating: google play reviews stored up to {latest}" if since else "full collection")

    with ThreadPoolExecutor(max_workers=1) as pool:
        apple = pool.submit(fetch_apple)
        play = fetch_play(1_000_000 if since else play_count, since)
        rows = apple.result() + play

    db.executemany(
        f"INSERT OR REPLACE INTO reviews VALUES ({','.join('?' * len(FIELDS))})",
        [[r[k] for k in FIELDS] for r in rows],
    )
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]

    with open(OUT / "reviews.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(db.execute(f"SELECT {', '.join(FIELDS)} FROM reviews"))
    db.close()
    new = sum(r["review_id"] not in known for r in play)
    print(f"done in {time.time() - start:.1f}s: {new:,} new google play reviews, "
          f"{total:,} reviews stored")
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--play-count", type=int, default=5000)
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    run(args.play_count, args.full)


if __name__ == "__main__":
    main()
