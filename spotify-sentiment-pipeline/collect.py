"""Collect Spotify reviews from the Apple App Store (iTunes RSS) and Google Play.

Writes data/reviews.csv and data/spotify_reviews.db (SQLite, table `reviews`).
Usage: python3 collect.py [--play-count 5000]
"""
import argparse
import csv
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

from google_play_scraper import Sort, reviews as play_reviews

APPLE_ID = "324684580"
PLAY_ID = "com.spotify.music"
OUT = Path(__file__).parent / "data"

FIELDS = [
    "review_id", "source", "company", "product", "rating", "review_title",
    "review_text", "review_date", "app_version", "developer_reply",
    "developer_reply_date", "thumbs_up",
]


def fetch_apple(country="us"):
    rows = {}
    for sort in ("mostRecent", "mostHelpful"):
        for page in range(1, 11):
            url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
                   f"page={page}/id={APPLE_ID}/sortBy={sort}/json")
            try:
                data = json.load(urllib.request.urlopen(url, timeout=30))
            except Exception as exc:  # feed returns errors past the last page
                print(f"apple {sort} p{page}: stopped ({exc})")
                break
            entries = data.get("feed", {}).get("entry", [])
            if isinstance(entries, dict):
                entries = [entries]
            added = 0
            for e in entries:
                if "im:rating" not in e:  # first entry can be app metadata
                    continue
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
                added += 1
            print(f"apple {sort} p{page}: {added} rows")
            if not entries:
                break
            time.sleep(0.5)
    return list(rows.values())


def fetch_play(target):
    rows, token = {}, None
    while len(rows) < target:
        batch, token = play_reviews(
            PLAY_ID, lang="en", country="us", sort=Sort.NEWEST,
            count=min(200, target - len(rows)), continuation_token=token,
        )
        for r in batch:
            rid = "play_" + r["reviewId"]
            rows[rid] = {
                "review_id": rid,
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
        print(f"play: {len(rows)} rows")
        if not batch or token is None:
            break
        time.sleep(1)
    return list(rows.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--play-count", type=int, default=5000)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    rows = fetch_apple() + fetch_play(args.play_count)

    with open(OUT / "reviews.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    db = sqlite3.connect(OUT / "spotify_reviews.db")
    db.execute("DROP TABLE IF EXISTS reviews")
    db.execute(
        "CREATE TABLE reviews (review_id TEXT PRIMARY KEY, source TEXT, company TEXT, "
        "product TEXT, rating INTEGER, review_title TEXT, review_text TEXT, review_date TEXT, "
        "app_version TEXT, developer_reply TEXT, developer_reply_date TEXT, thumbs_up INTEGER)"
    )
    db.executemany(
        f"INSERT INTO reviews VALUES ({','.join('?' * len(FIELDS))})",
        [[r[k] for k in FIELDS] for r in rows],
    )
    db.commit()
    db.close()
    print(f"done: {len(rows)} total rows")


if __name__ == "__main__":
    main()
