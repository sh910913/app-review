import unittest

from app_review.translate import (
    TranslateError,
    split_translation,
    translate_texts,
    translation_from_payload,
)


class TranslationPayloadTest(unittest.TestCase):
    def test_joins_segments(self) -> None:
        payload = [
            [
                ["按鈕很小", "ボタン", None],
                ["而且反應遲鈍。", "反応しない", None],
            ]
        ]
        self.assertEqual(translation_from_payload(payload), "按鈕很小而且反應遲鈍。")

    def test_rejects_empty_payload(self) -> None:
        with self.assertRaises(TranslateError):
            translation_from_payload([])


class SplitTranslationTest(unittest.TestCase):
    def test_splits_on_marker(self) -> None:
        translated = "Buttons are small\n⟦⟧\nThe content is good."
        self.assertEqual(
            split_translation(translated, 2),
            ["Buttons are small", "The content is good."],
        )

    def test_rejects_a_short_split(self) -> None:
        self.assertIsNone(split_translation("only one", 2))


class TranslateTextsTest(unittest.TestCase):
    def test_rejects_unknown_language_before_any_request(self) -> None:
        with self.assertRaises(TranslateError):
            translate_texts(["hello"], "nope")

    def test_empty_text_skips_the_service(self) -> None:
        self.assertEqual(translate_texts(["", ""], "en"), ["", ""])


if __name__ == "__main__":
    unittest.main()
