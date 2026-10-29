"""Streamlit dashboard over the review database.

Run after collect.py and process.py:  streamlit run app.py
"""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB = Path(__file__).parent / "data" / "spotify_reviews.db"


@st.cache_data
def query(sql, params=()):
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql(sql, con, params=params)
    finally:
        con.close()


st.title("Spotify review sentiment")

if not DB.exists():
    st.error("Database not found. Run collect.py first.")
    st.stop()

try:
    sources = query("SELECT DISTINCT source FROM reviews")["source"].tolist()
    query("SELECT 1 FROM review_sentiment LIMIT 1")
except Exception:
    st.error("Sentiment tables not found. Run process.py first.")
    st.stop()

source = st.sidebar.selectbox("Source", sources)

summary = query(
    "SELECT COUNT(*) AS reviews, ROUND(AVG(rating), 2) AS avg_rating, "
    "SUM(rating <= 2) AS negative FROM reviews WHERE source = ?", (source,))
c1, c2, c3 = st.columns(3)
c1.metric("Reviews", int(summary.at[0, "reviews"]))
c2.metric("Average rating", float(summary.at[0, "avg_rating"]))
c3.metric("Negative (1-2 stars)", int(summary.at[0, "negative"]))

st.subheader("Average sentiment by day")
trend = query(
    "SELECT date(r.review_date) AS day, ROUND(AVG(s.sentiment), 3) AS avg_sentiment "
    "FROM reviews r JOIN review_sentiment s USING (review_id) "
    "WHERE r.source = ? GROUP BY day ORDER BY day", (source,))
st.line_chart(trend, x="day", y="avg_sentiment")

st.subheader("Rolling 7-day negative reviews")
rolling = query(
    "WITH daily AS (SELECT date(review_date) AS day, SUM(rating <= 2) AS negative "
    "FROM reviews WHERE source = ? GROUP BY day) "
    "SELECT day, ROUND(AVG(negative) OVER (ORDER BY day "
    "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS neg_7d_avg "
    "FROM daily ORDER BY day", (source,))
st.line_chart(rolling, x="day", y="neg_7d_avg")

st.subheader("Features with the most negative reviews")
features = query(
    "SELECT f.feature, COUNT(*) AS negative_reviews "
    "FROM review_features f JOIN reviews r USING (review_id) "
    "WHERE r.rating <= 2 AND r.source = ? "
    "GROUP BY f.feature ORDER BY negative_reviews DESC", (source,))
st.bar_chart(features, x="feature", y="negative_reviews")

st.subheader("Most helpful negative reviews")
top = query(
    "SELECT date(review_date) AS date, rating, thumbs_up, review_text FROM reviews "
    "WHERE rating <= 2 AND source = ? ORDER BY thumbs_up DESC LIMIT 10", (source,))
st.dataframe(top, hide_index=True)
