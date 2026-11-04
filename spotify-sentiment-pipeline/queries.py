import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st

DB = Path(__file__).parent / "data" / "spotify_reviews.db"

NEGATIVE = "rating <= 2"

STORES = {"google_play": "Google Play", "app_store": "App Store"}

FEATURE_LABELS = {
    "pricing": "Pricing",
    "ads": "Ads",
    "crashes": "Crashes and bugs",
    "ui_update": "Updates and UI",
    "offline": "Offline and downloads",
    "shuffle": "Shuffle",
    "recommendations": "Recommendations",
    "login": "Login and account",
    "search": "Search",
    "playback": "Playback",
}


def _mtime():
    return DB.stat().st_mtime if DB.exists() else 0.0


@st.cache_data(show_spinner=False)
def _read(sql, params, mtime):
    with closing(sqlite3.connect(DB)) as con:
        return pd.read_sql(sql, con, params=params)


def read(sql, params=()):
    return _read(sql, tuple(params), _mtime())


def status():
    if not DB.exists():
        return "No database yet. Run `python collect.py` first."
    tables = set(read("SELECT name FROM sqlite_master WHERE type = 'table'")["name"])
    if "reviews" not in tables:
        return "The database has no reviews table. Run `python collect.py` first."
    if not {"review_sentiment", "review_features"} <= tables:
        return "Reviews are not processed yet. Run `python process.py` first."
    return None


def overview():
    df = read(f"""
        SELECT source,
               COUNT(*) AS reviews,
               AVG(rating) AS avg_rating,
               AVG({NEGATIVE}) AS neg_share,
               SUM({NEGATIVE}) AS negative,
               MIN(review_date) AS first_date,
               MAX(review_date) AS last_date
        FROM reviews GROUP BY source""")
    df["store"] = df["source"].map(STORES)
    for col in ("first_date", "last_date"):
        df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601")
    return df


def feature_stats(source):
    df = read(f"""
        SELECT f.feature,
               COUNT(*) AS mentions,
               SUM(r.{NEGATIVE}) AS negative,
               AVG(r.{NEGATIVE}) AS neg_share,
               AVG(r.rating) AS avg_rating
        FROM review_features f JOIN reviews r USING (review_id)
        WHERE r.source = ?
        GROUP BY f.feature""", (source,))
    total_negative = read(
        f"SELECT SUM({NEGATIVE}) AS n FROM reviews WHERE source = ?", (source,))["n"][0]
    df["share_of_all_negative"] = df["negative"] / total_negative
    df["label"] = df["feature"].map(FEATURE_LABELS).fillna(df["feature"])
    return df.sort_values("negative", ascending=False).reset_index(drop=True)


def baseline_neg_share(source):
    return float(read(f"""
        SELECT AVG({NEGATIVE}) AS share FROM reviews
        WHERE source = ?
          AND review_id NOT IN (SELECT review_id FROM review_features)""",
        (source,))["share"][0])


def rating_split():
    df = read("""
        SELECT source, rating, COUNT(*) AS reviews
        FROM reviews GROUP BY source, rating""")
    df["share"] = df["reviews"] / df.groupby("source")["reviews"].transform("sum")
    df["store"] = df["source"].map(STORES)
    return df


def daily(source="google_play"):
    df = read(f"""
        SELECT date(review_date) AS day,
               COUNT(*) AS reviews,
               SUM({NEGATIVE}) AS negative,
               AVG({NEGATIVE}) AS neg_share
        FROM reviews WHERE source = ?
        GROUP BY day ORDER BY day""", (source,))
    df["day"] = pd.to_datetime(df["day"])
    return df


def versions(source="google_play", min_reviews=100):
    df = read(f"""
        SELECT app_version, COUNT(*) AS reviews, AVG({NEGATIVE}) AS neg_share,
               AVG(rating) AS avg_rating
        FROM reviews
        WHERE source = ? AND app_version IS NOT NULL
        GROUP BY app_version HAVING COUNT(*) >= ?""", (source, min_reviews))
    key = df["app_version"].map(lambda v: tuple(int(p) for p in v.split(".") if p.isdigit()))
    df = df.assign(_key=key).sort_values("_key").drop(columns="_key")
    df["version"] = df["app_version"].map(lambda v: ".".join(v.split(".")[:3]))
    return df.reset_index(drop=True)


def replies(source="google_play"):
    return read("""
        SELECT rating, COUNT(*) AS reviews,
               SUM(developer_reply IS NOT NULL) AS replied,
               AVG(developer_reply IS NOT NULL) AS reply_rate
        FROM reviews WHERE source = ?
        GROUP BY rating ORDER BY rating""", (source,))


def reply_hours(source="google_play"):
    df = read("""
        SELECT review_date, developer_reply_date FROM reviews
        WHERE source = ? AND developer_reply_date IS NOT NULL""", (source,))
    start = pd.to_datetime(df["review_date"], utc=True, format="ISO8601")
    end = pd.to_datetime(df["developer_reply_date"], utc=True, format="ISO8601")
    return ((end - start).dt.total_seconds() / 3600).clip(lower=0)


def negative_reviews(source, feature, limit=6):
    return read(f"""
        SELECT r.review_date, r.rating, r.thumbs_up, r.app_version, r.review_text
        FROM reviews r JOIN review_features f USING (review_id)
        WHERE r.source = ? AND f.feature = ? AND r.{NEGATIVE}
        ORDER BY r.thumbs_up DESC, length(r.review_text) DESC
        LIMIT ?""", (source, feature, limit))


def sentiment_by_rating():
    return read("""
        SELECT r.rating, AVG(s.sentiment) AS vader, COUNT(*) AS reviews
        FROM reviews r JOIN review_sentiment s USING (review_id)
        GROUP BY r.rating ORDER BY r.rating""")


def tagged_share():
    return float(read("""
        SELECT AVG(review_id IN (SELECT review_id FROM review_features)) AS share
        FROM reviews""")["share"][0])
