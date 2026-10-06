# app-review

Look up the public App Store reviews for any app, across countries. You do not need to own the app, and you do not need an Apple developer account.

Reviews belong to the store where they were written. The same app has a separate list in Japan, the United States, Taiwan, and every other storefront. This tool checks each store, then downloads the written reviews from the stores that have ratings.

You need Python 3.11 or newer, and a network connection.

## Website

From this folder, start the site:

```bash
python3 -m app_review.web
```

Open http://127.0.0.1:8765.

Paste an App Store link or a numeric app id, then choose **查看評論**. A link looks like this:

```text
https://apps.apple.com/jp/app/id443332137
```

The number after `id` is the app id. `443332137` alone works too.

The page lists the public listing Apple already publishes: icon, price, release and update dates, description, and screenshots. It also shows which countries have the ratings, and the written reviews. Estimated downloads and estimated revenue are not in Apple's public data, so this page does not show them. You can filter by country and star rating, search the text, and load more than the first page. **Try Reeder** fills in Reeder, a well-known reading app with a smaller review set, as an example.

The page language follows your browser, and the same control translates the reviews. It sits in the header, beside the title, on the same column as the rest of the page. On a phone it moves under the title and spans the column. Choose **Original** to show each review in the language it was written. Translation uses Google Translate, with no API key. The original text stays under each translated review.

To use another port:

```bash
python3 -m app_review.web --port 9000
```

## Command line

The same lookup can write a file instead of opening the site.

```bash
python3 -m app_review "https://apps.apple.com/jp/app/id443332137" --out reviews.json
python3 -m app_review 443332137 --format csv --out reviews.csv
python3 -m app_review 443332137 --countries jp,tw,us --out reviews.json
```

Without `--out`, the file contents go to the terminal. Progress messages go to the error stream, so they stay out of the file.

`--sort` is `mostrecent` (the default) or `mosthelpful`. `--format` is `json` or `csv`.

## What you get, and what you do not

Apple’s public feed returns at most 10 pages of 50 reviews per country: about the 500 most recent written reviews. Star ratings with no text are not included. Older history is only available to the app’s developer in App Store Connect.

A country with zero ratings is skipped. Some apps have reviews in only one store.
