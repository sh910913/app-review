import unittest

from app_review.itunes import AppNotFound, InvalidAppId
from app_review.translate import TranslateError
from app_review.web import _ERROR_CODE


class ErrorCodeTest(unittest.TestCase):
    def test_invalid_app(self) -> None:
        self.assertEqual(_ERROR_CODE[InvalidAppId], "invalid_app")

    def test_not_found(self) -> None:
        self.assertEqual(_ERROR_CODE[AppNotFound], "not_found")

    def test_translate_code(self) -> None:
        error = TranslateError("busy")
        self.assertEqual(error.code, "busy")


if __name__ == "__main__":
    unittest.main()
