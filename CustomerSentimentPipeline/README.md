# Customer sentiment pipeline

Finds which product features draw the most complaints in Spotify's app reviews, and whether sentiment is changing over time. Reviews come from the Apple App Store and Google Play. A SQLite database holds the raw and processed data, Python scores and tags each review, and Streamlit shows the results.

## Pipeline

1. **`collect.py`** pulls reviews into `data/spotify_reviews.db` (table `reviews`) and `data/reviews.csv`.
   - App Store: Apple's public iTunes review feed, the 500 newest and 500 most helpful reviews.
   - Google Play: the `google-play-scraper` package, newest first. The default is 5,000 reviews, which covers about a week.
2. **`process.py`** reads `reviews` and writes two tables:
   - `review_sentiment`: VADER compound score per review.
   - `review_features`: one row per feature a review mentions (ads, pricing, shuffle, offline, search, login, crashes, playback, recommendations, ui_update), found with keyword rules.
3. **`app.py`** is a Streamlit dashboard: sentiment by day, a rolling 7-day count of negative reviews, features ranked by negative reviews, and the most helpful negative reviews.

## Run it

```
pip install -r requirements.txt
python3 collect.py --play-count 30000
python3 process.py
streamlit run app.py
```

A larger `--play-count` gives a longer time series. Spotify gets several hundred Google Play reviews a day, so 30,000 covers roughly a month.

## Schema

`reviews`: `review_id`, `source`, `company`, `product`, `rating`, `review_title`, `review_text`, `review_date`, `app_version`, `developer_reply`, `developer_reply_date`, `thumbs_up`.

Negative means a rating of 1 or 2 stars. App Store rows have no developer replies. Google Play rows have no review titles.

## Example query

Rolling 7-day average of negative reviews per source:

```sql
WITH daily AS (
  SELECT source, date(review_date) AS day, SUM(rating <= 2) AS negative
  FROM reviews GROUP BY source, day
)
SELECT source, day, negative,
       ROUND(AVG(negative) OVER (PARTITION BY source ORDER BY day
             ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS neg_7d_avg
FROM daily ORDER BY source, day;
```

## Known limits

- Keyword rules tag about a third of reviews. Zero-shot classification or BERTopic would cover more.
- VADER scores short, informal reviews near zero, so the star rating is the better negative label.
- Apple's feed returns at most about 500 reviews per sort order, so the App Store data is thin over time.
- Only the sample (`data/sample_reviews.csv`, 100 rows per source) is committed. Run `collect.py` to build the full dataset. Check each store's terms before publishing review text.
