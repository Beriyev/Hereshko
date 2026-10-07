import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import IngestionError
from app.services.video import pipeline
from yt_dlp.cookies import CookieLoadError
from yt_dlp.utils import DownloadError


class YouTubeDownloaderTests(unittest.TestCase):
    def setUp(self):
        settings = SimpleNamespace(
            yt_cookies_browser="opera-gx",
            yt_cookies_profile="custom-profile",
            yt_cookies_file="",
            yt_cookies_keyring="",
            yt_cookies_container="",
            yt_player_client="",
            yt_js_runtime="",
        )
        self.settings = settings
        self.settings_patch = patch.object(pipeline, "settings", settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.clients = []
        self.options = []

    def factory(self, options):
        self.options.append(options)
        client = MagicMock()
        client.__enter__.return_value = client
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            client.extract_info.side_effect = result
        else:
            client.extract_info.return_value = result
        self.clients.append(client)
        return client

    def extract(self, responses):
        self.responses = list(responses)
        with patch.object(pipeline.yt_dlp, "YoutubeDL", side_effect=self.factory):
            return pipeline._extract_youtube_info("https://youtu.be/3zqwlr8sp2Y", {}, download=True)

    def test_public_video_skips_configured_browser(self):
        self.assertEqual(self.extract([{"title": "Public video"}])["title"], "Public video")
        self.assertEqual(len(self.options), 1)
        self.assertNotIn("cookiesfrombrowser", self.options[0])
        self.assertNotIn("cookiefile", self.options[0])
        self.assertNotIn("extractor_args", self.options[0])

    def test_public_video_ignores_missing_cookie_file(self):
        self.settings.yt_cookies_file = "missing-cookies-for-test.txt"
        self.assertEqual(self.extract([{"title": "Public video"}])["title"], "Public video")

    def test_sign_in_failure_retries_with_configured_browser(self):
        result = self.extract([DownloadError("Sign in to confirm you're not a bot"), {"title": "Video"}])
        self.assertEqual(result["title"], "Video")
        self.assertNotIn("cookiesfrombrowser", self.options[0])
        self.assertEqual(self.options[1]["cookiesfrombrowser"], ("opera", "custom-profile", None, None))
        self.assertNotIn("extractor_args", self.options[1])

    def test_unavailable_video_does_not_retry_with_cookies(self):
        with self.assertRaises(IngestionError):
            self.extract([DownloadError("Video unavailable")])
        self.assertEqual(len(self.options), 1)

    def test_no_credentials_does_not_retry(self):
        self.settings.yt_cookies_browser = ""
        with self.assertRaises(IngestionError):
            self.extract([DownloadError("Sign in to confirm you're not a bot")])
        self.assertEqual(len(self.options), 1)

    def test_cookie_lock_is_reported_as_ingestion_error(self):
        with self.assertRaisesRegex(IngestionError, "cookie fallback failed"):
            self.extract([DownloadError("Sign in"), CookieLoadError("Could not copy cookie database")])


if __name__ == "__main__":
    unittest.main()
