import re
import threading
import time

import pandas as pd
import streamlit as st

import charts
import collect
import process
import queries as q

FIRST_COLLECTION = 30000
REFRESH_AFTER = 24 * 3600

st.set_page_config(page_title="spotify review sentiment", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2.5rem; padding-bottom: 4rem;}
[data-testid="stMetric"] {background: #161615;}
[data-testid="stMetricLabel"] p {color: #9a9890; font-size: 0.85rem;}
[data-testid="stMetricValue"] {font-weight: 600; letter-spacing: -0.01em;}
[data-testid="stCaptionContainer"] {color: #9a9890;}
[data-testid="stExpander"] details {background: #121211;}
h1 {letter-spacing: -0.02em;}
h2 {margin-top: 1.75rem; letter-spacing: -0.01em;}
#vg-tooltip-element {background: #1c1c1b !important; color: #f0efec !important;
  border: 1px solid #2c2c2a !important; border-radius: 8px !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.45) !important; font-family: system-ui, sans-serif !important;}
#vg-tooltip-element td.key {color: #9a9890 !important;}
</style>
""", unsafe_allow_html=True)


def fmt_day(ts):
    return f"{ts:%b} {ts.day}".lower()


def md_escape(text):
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~<$])", r"\\\1", str(text))


def chart(c):
    st.altair_chart(c, theme=None, width="stretch")


def view_data(df, columns):
    with st.expander("view data"):
        st.dataframe(df[list(columns)].rename(columns=columns), hide_index=True)


def render_header(ov):
    gp = ov.set_index("source").loc["google_play"]
    total = int(ov["reviews"].sum())
    st.title("spotify review sentiment")
    st.caption(
        f"{total:,} app reviews. google play: {int(gp.reviews):,} reviews from "
        f"{fmt_day(gp.first_date)} to {fmt_day(gp.last_date)}, {gp.last_date.year}. "
        f"app store: {int(ov.set_index('source').loc['app_store', 'reviews']):,} of the newest "
        f"and most helpful reviews."
    )

    avg = (ov["avg_rating"] * ov["reviews"]).sum() / total
    neg = ov["negative"].sum() / total
    hours = q.reply_hours()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("reviews analyzed", f"{total:,}", border=True,
              help=", ".join(f"{int(r.reviews):,} {r.store}" for r in ov.itertuples()))
    c2.metric("average rating", f"{avg:.2f} / 5", border=True)
    c3.metric("negative reviews", f"{neg:.0%}", border=True,
              help="reviews rated 1 or 2 stars")
    c4.metric("median reply time", f"{hours.median():.0f} hours", border=True,
              help=f"google play, based on {len(hours):,} developer replies")


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
        f"**most complaints:** {top.label.iloc[0]} and {top.label.iloc[1]}. "
        f"{top.label.iloc[0]} comes up in {top.share_of_all_negative.iloc[0]:.0%} of negative "
        f"google play reviews, {top.label.iloc[1]} in {top.share_of_all_negative.iloc[1]:.0%}.",
    ]
    if len(severe):
        labels = list(severe["label"])
        names = f"{', '.join(labels[:-1])} and {labels[-1]}" if len(labels) > 1 else labels[0]
        lines.append(
            f"**most damaging when mentioned:** {names}. "
            f"{severe.neg_share.min():.0%} to {severe.neg_share.max():.0%} of reviews that mention "
            f"them are negative, against {base:.0%} for reviews that mention no tracked feature.")
    if len(vers) >= 2:
        new, prev = vers.iloc[-1], vers.iloc[-2]
        lines.append(
            f"**latest version:** {new.version} has {new.neg_share:.0%} negative reviews, "
            f"against {prev.neg_share:.0%} on {prev.version}.")
    lines.append(
        f"**replies:** spotify replies to {low.replied.sum() / low.reviews.sum():.0%} of 1 and 2 star "
        f"reviews, with a median wait of {hours.median():.0f} hours. it almost never replies to "
        f"5 star reviews ({rep.loc[5, 'reply_rate']:.1%}).")
    lines.append(
        f"**trend:** the daily negative share stayed between {day.neg_share.min():.0%} and "
        f"{day.neg_share.max():.0%} over {len(day)} days. that is too short a window to show a direction.")

    with st.container(border=True):
        st.subheader("what the reviews say")
        st.caption("based on google play, the larger and more recent sample.")
        st.markdown("\n".join(f"- {line}" for line in lines))


def render_features():
    st.header("complaints by feature")
    st.caption("features are found with keyword rules. a review can mention more than one. "
               "negative means 1 or 2 stars.")
    source = st.segmented_control("store", list(q.STORES), format_func=q.STORES.get,
                                  default="google_play", required=True)
    feats = q.feature_stats(source)
    base = q.baseline_neg_share(source)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("where the negative reviews are")
        st.caption("number of negative reviews that mention each feature.")
        chart(charts.feature_volume(feats))
        view_data(feats, {"label": "feature", "negative": "negative reviews",
                          "share_of_all_negative": "share of all negative reviews"})
    with right:
        st.subheader("how often a mention is negative")
        st.caption("share of reviews mentioning the feature that are negative. "
                   "total mentions in brackets.")
        chart(charts.feature_severity(feats, base))
        view_data(feats.sort_values("neg_share", ascending=False),
                  {"label": "feature", "mentions": "reviews mentioning it",
                   "neg_share": "share negative"})

    render_explorer(source, feats)


def render_explorer(source, feats):
    st.subheader("read the complaints")
    feature = st.selectbox("feature", feats["feature"].tolist(),
                           format_func=dict(zip(feats.feature, feats.label)).get)
    reviews = q.negative_reviews(source, feature)
    if reviews.empty:
        st.caption("no negative reviews mention this feature in this store.")
        return
    st.caption(f"the most helpful negative {q.STORES[source]} reviews that mention it.")
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


def render_ratings():
    st.header("how ratings split")
    split = q.rating_split()
    stores = [q.STORES[s] for s in q.STORES if s in set(split["source"])]
    gp = split[split["source"] == "google_play"].set_index("rating")["share"]
    if len(gp) == 5:
        st.caption(
            f"ratings are polarized. on google play, {gp[5]:.0%} of reviews give 5 stars and "
            f"{gp[1]:.0%} give 1 star, while only {gp[2] + gp[3] + gp[4]:.0%} land in between. "
            "bars are centered on the middle of 3 stars, so negative reviews extend left.")
    chart(charts.rating_split(split, stores))
    view_data(split.sort_values(["store", "rating"]),
              {"store": "store", "rating": "stars", "reviews": "reviews", "share": "share"})


def render_time_and_versions():
    st.header("over time and by version")
    st.caption("google play only. the app store sample is its newest and most helpful "
               "reviews, so it does not form a continuous timeline.")
    day = q.daily()
    vers = q.versions()
    avg = day["negative"].sum() / day["reviews"].sum()

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("negative share by day")
        st.caption(f"between {day.neg_share.min():.0%} and {day.neg_share.max():.0%} each day, "
                   f"with no clear direction over one week. the gray line is the week's "
                   f"average, {avg:.0%}.")
        chart(charts.daily_trend(day, avg))
        view_data(day.assign(day=day["day"].dt.date),
                  {"day": "day", "reviews": "reviews", "negative": "negative",
                   "neg_share": "share negative"})
    with right:
        st.subheader("negative share by app version")
        if len(vers) >= 2:
            new, prev = vers.iloc[-1], vers.iloc[-2]
            diff = (new.neg_share - prev.neg_share) * 100
            direction = "more" if diff >= 0 else "fewer"
            st.caption(f"version {new.version} has {abs(diff):.0f} points {direction} negative "
                       f"reviews than {prev.version}. versions with at least 100 reviews.")
        else:
            st.caption("versions with at least 100 reviews.")
        if len(vers):
            chart(charts.version_compare(vers))
            view_data(vers, {"app_version": "version", "reviews": "reviews",
                             "neg_share": "share negative", "avg_rating": "average rating"})


def render_replies():
    st.header("how spotify replies")
    rep = q.replies()
    hours = q.reply_hours()
    low = rep[rep["rating"] <= 2]
    st.caption(
        f"google play only; the app store feed does not include replies. spotify replied to "
        f"{low.replied.sum() / low.reviews.sum():.0%} of 1 and 2 star reviews and to almost no "
        f"5 star reviews, so replies go where the complaints are.")
    left, right = st.columns([2, 1], gap="large")
    with left:
        st.subheader("share of reviews with a reply")
        chart(charts.reply_rate(rep))
        view_data(rep, {"rating": "stars", "reviews": "reviews", "replied": "replies",
                        "reply_rate": "reply rate"})
    with right:
        st.subheader("time to reply")
        st.metric("median", f"{hours.median():.0f} hours", border=True,
                  help="time between the review and spotify's reply")
        st.metric("within 24 hours", f"{(hours <= 24).mean():.0%}", border=True,
                  help=f"share of {len(hours):,} replies")
        st.caption(f"a quarter of replies arrive within {hours.quantile(0.25) * 60:.0f} minutes, "
                   f"three quarters within {hours.quantile(0.75):.0f} hours.")


def render_method():
    vader = q.sentiment_by_rating().set_index("rating")["vader"]
    with st.expander("how this was measured"):
        st.markdown(f"""
- **sources:** google play reviews come from the `google-play-scraper` package, newest first. app store reviews come from apple's public review feed, which only serves the 500 newest and 500 most helpful reviews.
- **negative:** a review rated 1 or 2 stars. the star rating is the main signal on this page.
- **features:** keyword rules in `process.py`. they matched {q.tagged_share():.0%} of reviews. a review can match several features, the rules miss some phrasings, and broad words like "pay" catch some reviews that are about something else.
- **sentiment score:** vader averages {vader.get(1, float('nan')):.2f} on 1 star reviews and {vader.get(5, float('nan')):.2f} on 5 star reviews, on a scale from -1 to 1. it reads many short or sarcastic complaints as neutral, which is why the charts use star ratings instead.
- **reply time:** hours between a review and spotify's reply, from the timestamps google play shows.
""")


@st.cache_resource
def build_lock():
    return threading.Lock()


def needs_build():
    if q.status():
        return "missing"
    if time.time() - q.DB.stat().st_mtime > REFRESH_AFTER:
        return "stale"
    return None


def ensure_data():
    if not needs_build():
        return
    lock = build_lock()
    if not lock.acquire(blocking=False):
        with st.spinner("reviews are being collected. this takes about half a minute."):
            lock.acquire()
    try:
        need = needs_build()
        if not need:
            return
        label = ("collecting reviews for the first time. this takes about half a minute."
                 if need == "missing" else "adding the latest reviews.")
        try:
            with st.status(label) as box:
                box.write("downloading reviews from google play and the app store")
                collect.run(play_count=FIRST_COLLECTION)
                box.write("scoring sentiment and tagging features")
                process.main()
                box.update(label="reviews ready", state="complete")
        except Exception as exc:
            if need == "missing" or q.status():
                st.error(f"couldn't collect reviews: {exc}")
                st.stop()
            st.warning(f"couldn't add the latest reviews, showing the stored ones. ({exc})")
            return
    finally:
        lock.release()
    st.rerun()


def main():
    ensure_data()
    problem = q.status()
    if problem:
        st.title("spotify review sentiment")
        st.info(problem)
        st.stop()

    render_header(q.overview())
    render_findings()
    render_features()
    render_ratings()
    render_time_and_versions()
    render_replies()
    render_method()


main()
