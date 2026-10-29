"""Spotify review sentiment dashboard.

Run after collect.py and process.py:  python -m streamlit run app.py
"""
import re

import pandas as pd
import streamlit as st

import charts
import queries as q

st.set_page_config(page_title="Spotify review sentiment", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2.5rem; padding-bottom: 4rem;}
[data-testid="stMetricLabel"] p {color: #52514e; font-size: 0.85rem;}
[data-testid="stMetricValue"] {font-weight: 600;}
[data-testid="stCaptionContainer"] {color: #52514e;}
h2 {margin-top: 1.75rem;}
</style>
""", unsafe_allow_html=True)


def lower_first(text):
    """Lowercase the first letter only, so acronyms like UI keep their case."""
    return text[:1].lower() + text[1:]


def fmt_day(ts):
    return f"{ts:%b} {ts.day}"


def md_escape(text):
    """Show review text literally; reviews are user content, not markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<$])", r"\\\1", str(text))


def chart(c):
    st.altair_chart(c, theme=None, width="stretch")


def view_data(df, columns):
    with st.expander("View data"):
        st.dataframe(df[list(columns)].rename(columns=columns), hide_index=True)


# ---------------------------------------------------------------- header

def render_header(ov):
    gp = ov.set_index("source").loc["google_play"]
    total = int(ov["reviews"].sum())
    st.title("Spotify review sentiment")
    st.caption(
        f"{total:,} app reviews. Google Play: {int(gp.reviews):,} reviews from "
        f"{fmt_day(gp.first_date)} to {fmt_day(gp.last_date)}, {gp.last_date.year}. "
        f"App Store: the 500 newest and 500 most helpful reviews."
    )

    avg = (ov["avg_rating"] * ov["reviews"]).sum() / total
    neg = ov["negative"].sum() / total
    hours = q.reply_hours()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reviews analyzed", f"{total:,}", border=True,
              help=", ".join(f"{int(r.reviews):,} {r.store}" for r in ov.itertuples()))
    c2.metric("Average rating", f"{avg:.2f} / 5", border=True)
    c3.metric("Negative reviews", f"{neg:.0%}", border=True,
              help="Reviews rated 1 or 2 stars")
    c4.metric("Median reply time", f"{hours.median():.0f} hours", border=True,
              help=f"Google Play, based on {len(hours):,} developer replies")


# ---------------------------------------------------------------- findings

def render_findings():
    feats = q.feature_stats("google_play")
    base = q.baseline_neg_share("google_play")
    top = feats.head(2)
    severe = feats[(feats["neg_share"] >= 0.6) & (feats["mentions"] >= 20)]
    vers = q.versions()
    rep = q.replies().set_index("rating")
    low = rep.loc[[1, 2]]
    day = q.daily()
    hours = q.reply_hours()

    lines = [
        f"**Most complaints:** {top.label.iloc[0]} and {lower_first(top.label.iloc[1])}. "
        f"{top.label.iloc[0]} comes up in {top.share_of_all_negative.iloc[0]:.0%} of negative "
        f"Google Play reviews, {lower_first(top.label.iloc[1])} in {top.share_of_all_negative.iloc[1]:.0%}.",
    ]
    if len(severe):
        labels = [lower_first(x) for x in severe["label"]]
        names = f"{', '.join(labels[:-1])} and {labels[-1]}" if len(labels) > 1 else labels[0]
        lines.append(
            f"**Most damaging when mentioned:** {names}. "
            f"{severe.neg_share.min():.0%} to {severe.neg_share.max():.0%} of reviews that mention "
            f"them are negative, against {base:.0%} for reviews that mention no tracked feature.")
    if len(vers) >= 2:
        new, prev = vers.iloc[-1], vers.iloc[-2]
        lines.append(
            f"**Latest version:** {new.version} has {new.neg_share:.0%} negative reviews, "
            f"against {prev.neg_share:.0%} on {prev.version}.")
    lines.append(
        f"**Replies:** Spotify replies to {low.replied.sum() / low.reviews.sum():.0%} of 1 and 2 star "
        f"reviews, with a median wait of {hours.median():.0f} hours. It almost never replies to "
        f"5 star reviews ({rep.loc[5, 'reply_rate']:.1%}).")
    lines.append(
        f"**Trend:** The daily negative share stayed between {day.neg_share.min():.0%} and "
        f"{day.neg_share.max():.0%} over {len(day)} days. That is too short a window to show a direction.")

    with st.container(border=True):
        st.subheader("What the reviews say")
        st.caption("Based on Google Play, the larger and more recent sample.")
        st.markdown("\n".join(f"- {line}" for line in lines))


# ---------------------------------------------------------------- features

def render_features():
    st.header("Complaints by feature")
    st.caption("Features are found with keyword rules. A review can mention more than one. "
               "Negative means 1 or 2 stars.")
    source = st.segmented_control("Store", list(q.STORES), format_func=q.STORES.get,
                                  default="google_play", required=True)
    feats = q.feature_stats(source)
    base = q.baseline_neg_share(source)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Where the negative reviews are")
        st.caption("Number of negative reviews that mention each feature.")
        chart(charts.feature_volume(feats))
        view_data(feats, {"label": "Feature", "negative": "Negative reviews",
                          "share_of_all_negative": "Share of all negative reviews"})
    with right:
        st.subheader("How often a mention is negative")
        st.caption("Share of reviews mentioning the feature that are negative. "
                   "Total mentions in brackets.")
        chart(charts.feature_severity(feats, base))
        view_data(feats.sort_values("neg_share", ascending=False),
                  {"label": "Feature", "mentions": "Reviews mentioning it",
                   "neg_share": "Share negative"})

    render_explorer(source, feats)


def render_explorer(source, feats):
    st.subheader("Read the complaints")
    feature = st.selectbox("Feature", feats["feature"].tolist(),
                           format_func=dict(zip(feats.feature, feats.label)).get)
    reviews = q.negative_reviews(source, feature)
    if reviews.empty:
        st.caption("No negative reviews mention this feature in this store.")
        return
    st.caption(f"The most helpful negative {q.STORES[source]} reviews that mention it.")
    cols = st.columns(2, gap="medium")
    for i, r in enumerate(reviews.itertuples()):
        day = pd.to_datetime(r.review_date, utc=True, format="ISO8601")
        meta = [f"{r.rating} star" + ("" if r.rating == 1 else "s"),
                f"{fmt_day(day)}, {day.year}"]
        if r.thumbs_up:
            meta.append(f"{r.thumbs_up:,} found this helpful")
        if r.app_version:
            meta.append(f"version {'.'.join(str(r.app_version).split('.')[:3])}")
        with cols[i % 2].container(border=True):
            st.caption(" · ".join(meta))
            st.markdown(md_escape(r.review_text))


# ---------------------------------------------------------------- page

def main():
    problem = q.status()
    if problem:
        st.title("Spotify review sentiment")
        st.info(problem)
        st.stop()

    render_header(q.overview())
    render_findings()
    render_features()


main()
