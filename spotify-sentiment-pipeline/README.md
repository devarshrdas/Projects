# customer sentiment pipeline

finds which features draw the most complaints in spotify's app store and google play reviews, and whether sentiment is shifting over time.

sqlite holds the data, python scores and tags each review, streamlit shows the results.

## tech stack

- **language:** python
- **database:** sqlite, queried with sql window functions
- **data collection:** apple's itunes review feed (app store), `google-play-scraper` (google play)
- **data handling:** `pandas`, `sqlalchemy`
- **nlp:** `vaderSentiment` for sentiment, regex keyword rules for feature tags
- **dashboard:** `streamlit`

## run it

from this folder, in order:

```
python -m pip install -r requirements.txt
python collect.py --play-count 30000
python process.py
python -m streamlit run app.py
```

if `python` isn't found on windows, use `py` instead. on mac or linux, use `python3`.

## files

- `collect.py` pulls reviews into `data/spotify_reviews.db` (table `reviews`)
- `process.py` adds `review_sentiment` (vader score) and `review_features` (keyword tags like ads, pricing, shuffle, crashes)
- `app.py` is the dashboard: sentiment by day, rolling 7-day negative reviews, features ranked by complaints

## notes

- negative means 1 or 2 stars
- the app store feed caps at about 500 reviews per sort order, so its time series is thin
- keyword rules tag about a third of reviews. zero-shot classification would cover more
- only `data/sample_reviews.csv` is committed. run `collect.py` for the full set
