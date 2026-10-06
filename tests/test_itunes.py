import json
import unittest
from unittest.mock import patch

from app_review.itunes import (
    ItunesError,
    fetch_country_reviews,
    metadata_from_result,
    parse_app_id,
    reviews_from_feed,
)


class ParseAppIdTest(unittest.TestCase):
    def test_url(self) -> None:
        url = (
            "https://apps.apple.com/jp/app/"
            "%E3%81%A9%E3%82%93%E3%81%A9%E3%82%93/id443332137"
        )
        self.assertEqual(parse_app_id(url), "443332137")

    def test_bare_id(self) -> None:
        self.assertEqual(parse_app_id(" 443332137 "), "443332137")

    def test_rejects_junk(self) -> None:
        with self.assertRaises(ItunesError):
            parse_app_id("not-an-app")


class ReviewsFromFeedTest(unittest.TestCase):
    def test_skips_non_review_entries_and_reads_labels(self) -> None:
        payload = {
            "feed": {
                "entry": [
                    {"im:name": {"label": "the app itself"}},
                    {
                        "id": {"label": "99"},
                        "im:rating": {"label": "2"},
                        "title": {"label": "按鈕太小"},
                        "content": {"label": "不好按"},
                        "author": {"name": {"label": "ttt"}},
                        "im:version": {"label": "4.24"},
                        "updated": {"label": "2026-08-04T00:36:35-07:00"},
                        "im:voteCount": {"label": "3"},
                        "im:voteSum": {"label": "1"},
                    },
                ]
            }
        }
        reviews = reviews_from_feed(payload, "jp")
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].id, "99")
        self.assertEqual(reviews[0].rating, 2)
        self.assertEqual(reviews[0].author, "ttt")
        self.assertEqual(reviews[0].vote_count, 3)
        self.assertEqual(json.loads(json.dumps(reviews[0].as_dict()))["country"], "jp")

    def test_single_entry_object(self) -> None:
        payload = {
            "feed": {
                "entry": {
                    "id": {"label": "1"},
                    "im:rating": {"label": "5"},
                    "title": {"label": "good"},
                    "content": {"label": "yes"},
                }
            }
        }
        reviews = reviews_from_feed(payload, "us")
        self.assertEqual([review.rating for review in reviews], [5])

    def test_empty_feed(self) -> None:
        self.assertEqual(reviews_from_feed({"feed": {}}, "jp"), [])
        self.assertEqual(reviews_from_feed("nope", "jp"), [])


class PartialPageTest(unittest.TestCase):
    def test_keeps_reviews_when_a_later_page_is_blocked(self) -> None:
        def fake_get(url: str) -> str:
            if "page=1" in url:
                return json.dumps(
                    {
                        "feed": {
                            "entry": [
                                {
                                    "id": {"label": "1"},
                                    "im:rating": {"label": "5"},
                                    "title": {"label": "ok"},
                                    "content": {"label": "yes"},
                                }
                            ]
                        }
                    }
                )
            raise ItunesError(f"HTTP 403 for {url}")

        with patch("app_review.itunes._get_text", side_effect=fake_get) as get:
            batch = fetch_country_reviews("99", "ee", "mostrecent")
        self.assertEqual([review.id for review in batch.reviews], ["1"])
        self.assertTrue(batch.partial)
        self.assertFalse(batch.truncated)
        self.assertTrue(get.call_args_list[0].args[0].endswith("/json"))


class MetadataTest(unittest.TestCase):
    def test_reads_public_listing_fields(self) -> None:
        meta = metadata_from_result(
            {
                "artworkUrl512": "https://example/icon.jpg",
                "artistName": "Wikimedia",
                "formattedPrice": "Free",
                "price": 0,
                "genres": ["Reference", 3],
                "releaseDate": "2012-01-01T00:00:00Z",
                "currentVersionReleaseDate": "2026-09-01T00:00:00Z",
                "version": "7.0",
                "description": "Hello",
                "screenshotUrls": ["https://example/a.jpg", 1],
                "trackViewUrl": "https://apps.apple.com/us/app/id1",
                "averageUserRating": 4.5,
                "userRatingCount": 10,
            },
            "us",
        )
        self.assertEqual(meta["artwork"], "https://example/icon.jpg")
        self.assertEqual(meta["screenshots"], ["https://example/a.jpg"])
        self.assertEqual(meta["genres"], ["Reference"])
        self.assertEqual(meta["price_amount"], 0)
        self.assertEqual(meta["rating_count"], 10)
        self.assertEqual(meta["country"], "us")


if __name__ == "__main__":
    unittest.main()
