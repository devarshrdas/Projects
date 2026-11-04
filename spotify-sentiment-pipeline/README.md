# spotify customer sentiment pipeline

finds which features draw the most complaints in spotify's app store and google play reviews, and whether sentiment is shifting over time.

sqlite holds the data, python scores and tags each review, streamlit shows the results.

## tech stack

- **language:** python
- **database:** sqlite, queried with sql window functions
- **data collection:** apple's itunes review feed (app store), `google-play-scraper` (google play)
- **data handling:** `pandas`, `sqlalchemy`
- **nlp:** `vaderSentiment` for sentiment, regex keyword rules for feature tags
- **dashboard:** `streamlit`, `altair` for charts

## run it

from this folder, in order:

```
python -m pip install -r requirements.txt
python collect.py --play-count 30000
python process.py
python -m streamlit run app.py
```

if `python` isn't found on windows, use `py` instead. on mac or linux, use `python3`.

the first `collect.py` run pulls up to `--play-count` google play reviews, which takes about 12 seconds for 30,000. after that, running `python collect.py` only adds reviews newer than the ones already stored, usually in a second or two. run `python process.py` again after each update. to start over, use `python collect.py --full --play-count 30000`.

you can also skip straight to `python -m streamlit run app.py`. if there's no database, the app collects and processes 30,000 reviews itself, which takes about 20 seconds. it adds new reviews on its own once the data is more than a day old.

## deploy

on streamlit community cloud, create an app from this repo with branch `main` and main file path `spotify-sentiment-pipeline/app.py`. the app builds its own data on the first visit, so nothing else needs to be committed. community cloud reads the theme from `.streamlit/config.toml` at the root of the repo.

## files

- `collect.py` pulls reviews into `data/spotify_reviews.db` (table `reviews`)
- `process.py` adds `review_sentiment` (vader score) and `review_features` (keyword tags like ads, pricing, shuffle, crashes)
- `app.py` lays out the dashboard
- `queries.py` holds the sql behind each section
- `charts.py` builds the altair charts
- `.streamlit/config.toml` sets the theme when you run streamlit from this folder. the copy at the repo root is the one community cloud uses

## dashboard

- headline numbers and a short list of findings, written from the data
- complaints by feature: how many negative reviews mention each one, and how often a mention is negative
- the actual negative reviews behind any feature
- how ratings split in each store
- negative share by day and by app version
- how often and how fast spotify replies

every chart has a "view data" table under it

## notes

- negative means 1 or 2 stars
- the app store feed caps at about 500 reviews per sort order, so its time series is thin. updates keep adding to it over time
- keyword rules tag about a third of reviews. zero-shot classification would cover more
- only `data/sample_reviews.csv` is committed. run `collect.py` for the full set
