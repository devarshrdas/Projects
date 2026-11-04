import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DB = Path(__file__).parent / "data" / "spotify_reviews.db"

FEATURES = {
    "ads": r"\bads?\b|advert|commercial",
    "shuffle": r"shuffle",
    "playback": r"keeps? (pausing|stopping|skipping)|stops? playing|won'?t play|buffer",
    "offline": r"offline|download",
    "pricing": r"price|premium|subscription|expensive|cost|pay",
    "search": r"\bsearch",
    "login": r"log ?in|sign ?in|password|account",
    "crashes": r"crash|freez|glitch|\bbug|not working|doesn'?t work",
    "recommendations": r"recommend|algorithm|discover|daily mix|dj\b",
    "ui_update": r"update|new (ui|design|layout|version)|interface",
}


def main():
    engine = create_engine(f"sqlite:///{DB}")
    df = pd.read_sql("SELECT review_id, review_text FROM reviews", engine)

    sia = SentimentIntensityAnalyzer()
    df["sentiment"] = df["review_text"].map(lambda t: sia.polarity_scores(t)["compound"])

    tags = [
        (rid, feat)
        for rid, text in zip(df["review_id"], df["review_text"].str.lower())
        for feat, pat in FEATURES.items()
        if re.search(pat, text)
    ]

    df[["review_id", "sentiment"]].to_sql(
        "review_sentiment", engine, if_exists="replace", index=False)
    pd.DataFrame(tags, columns=["review_id", "feature"]).to_sql(
        "review_features", engine, if_exists="replace", index=False)

    tagged = len({rid for rid, _ in tags})
    print(f"scored {len(df)} reviews, tagged {tagged} with at least one feature")


if __name__ == "__main__":
    main()
