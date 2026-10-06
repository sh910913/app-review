# app-review

Read a competitor’s App Store reviews from every country, in your language.

For indie hackers, product managers, and founders gathering what customers actually wrote. A store page is one country. The same app has different reviews in Japan, the United States, Taiwan, and every other storefront. Paste one link and those reviews come back together, with a translation above the original.

A store page means changing the country code and translating by hand. Intelligence products sell download and revenue estimates. This reads the written reviews Apple already publishes.

You can see what people praise and what they keep complaining about, whether that shows up in one country or everywhere, and the phrases customers use.

Each country includes about the 500 most recent written reviews. Ratings with no text are left out. A country with no ratings is skipped. Estimated downloads and revenue are not in Apple’s public data.

## Run it

Python 3.11 or newer.

```bash
python3 -m app_review.web
```

Open http://127.0.0.1:8765. Paste an App Store link or an app id. **Try Reeder** loads a smaller example. The page follows your browser language. Choose **Original** to read each review as it was written.

```text
https://apps.apple.com/jp/app/id443332137
```

`443332137` alone works too.

```bash
python3 -m app_review.web --port 9000
python3 -m app_review 443332137 --out reviews.json
python3 -m app_review 443332137 --format csv --out reviews.csv
python3 -m app_review 443332137 --countries jp,tw,us --out reviews.json
```

`--sort` is `mostrecent` (the default) or `mosthelpful`. Without `--out`, reviews print to the terminal and progress goes to the error stream. Translation uses Google Translate, with no API key.
