from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from reviews import autoreview
from reviews.autoreview import (
    _find_invalid_isbns,
    _validate_isbn_10,
    _validate_isbn_13,
)
from reviews.models import EditorProfile, Wiki
from reviews.services import was_user_blocked_after


class GlobalBotAutoreviewTests(TestCase):
    """Test autoreview decisions for global and former global bots."""

    def setUp(self):
        """Set up common mock objects for the tests."""
        self.wiki = Wiki.objects.create(code="testwiki", name="Test Wiki")
        self.mock_client = MagicMock()
        self.mock_client.has_manual_unapproval.return_value = False
        self.mock_client.is_user_blocked_after_edit.return_value = False

        self.revision = MagicMock()
        self.revision.user_name = "TestUser"
        self.revision.page.title = "Test Page"
        self.revision.revid = 12345
        self.revision.page.wiki = self.wiki  # Use the real Wiki object
        self.revision.get_wikitext.return_value = ""  # No invalid ISBNs
        self.revision.superset_data = {}  # Ensure superset_data exists

        # Mock checks that run after the bot check to isolate the logic
        self.render_patcher = patch(
            "reviews.autoreview._check_for_new_render_errors", return_value=False
        )
        self.mock_render_check = self.render_patcher.start()
        self.addCleanup(self.render_patcher.stop)

    def test_global_bot_is_auto_approved(self):
        """Verify that a user marked as a global bot is auto-approved."""
        # Arrange: Create a profile for a global bot
        profile = EditorProfile(
            username="GlobalBotUser",
            is_bot=False,
            is_former_bot=False,
            is_global_bot=True,
            is_former_global_bot=False,
            is_autoreviewed=False,
            is_autopatrolled=False,
        )
        self.revision.user_name = "GlobalBotUser"

        # Act: Evaluate the revision
        result = autoreview._evaluate_revision(
            self.revision,
            self.mock_client,
            profile,
            auto_groups={},
            blocking_categories={},
            redirect_aliases=[],
        )

        # Assert: The decision should be 'approve' because the user is a bot
        self.assertEqual(result["decision"].status, "approve")
        self.assertIn("user is recognized as a bot", result["decision"].reason)
        bot_test = next(t for t in result["tests"] if t["id"] == "bot-user")
        self.assertEqual(bot_test["status"], "ok")

    def test_former_global_bot_is_auto_approved(self):
        """Verify that a user marked as a former global bot is auto-approved."""
        # Arrange: Create a profile for a former global bot
        profile = EditorProfile(
            username="FormerGlobalBotUser",
            is_bot=False,
            is_former_bot=False,
            is_global_bot=False,
            is_former_global_bot=True,
            is_autoreviewed=False,
            is_autopatrolled=False,
        )
        self.revision.user_name = "FormerGlobalBotUser"

        # Act: Evaluate the revision
        result = autoreview._evaluate_revision(
            self.revision,
            self.mock_client,
            profile,
            auto_groups={},
            blocking_categories={},
            redirect_aliases=[],
        )

        # Assert: The decision should be 'approve'
        self.assertEqual(result["decision"].status, "approve")
        self.assertIn("user is recognized as a bot", result["decision"].reason)

    def test_regular_user_with_no_bot_flags_is_not_approved_as_bot(self):
        """Verify a regular user is not approved based on bot status."""
        # Arrange: Create a profile for a regular user
        profile = EditorProfile.objects.create(
            wiki=self.wiki,
            username="RegularUser",
            is_bot=False,
            is_former_bot=False,
            is_global_bot=False,
            is_former_global_bot=False,
            is_autoreviewed=False,
            is_autopatrolled=False,
        )
        self.revision.user_name = "RegularUser"

        # Act: Evaluate the revision
        result = autoreview._evaluate_revision(
            self.revision,
            self.mock_client,
            profile,
            auto_groups={},
            blocking_categories={},
            redirect_aliases=[],
        )

        # Assert: The 'bot-user' test should fail, and the final status is 'manual'
        bot_test = next(t for t in result["tests"] if t["id"] == "bot-user")
        self.assertEqual(bot_test["status"], "not_ok")
        self.assertEqual(result["decision"].status, "manual")


class ISBNValidationTests(TestCase):
    """Test ISBN-10 and ISBN-13 checksum validation."""

    def test_valid_isbn_10_with_numeric_check_digit(self):
        """Valid ISBN-10 with numeric check digit should pass."""
        self.assertTrue(_validate_isbn_10("0306406152"))

    def test_valid_isbn_10_with_x_check_digit(self):
        """Valid ISBN-10 with 'X' check digit should pass."""
        self.assertTrue(_validate_isbn_10("043942089X"))
        self.assertTrue(_validate_isbn_10("043942089x"))  # lowercase x

    def test_invalid_isbn_10_wrong_checksum(self):
        """ISBN-10 with wrong checksum should fail."""
        self.assertFalse(_validate_isbn_10("0306406153"))  # Last digit wrong

    def test_invalid_isbn_10_too_short(self):
        """ISBN-10 with fewer than 10 digits should fail."""
        self.assertFalse(_validate_isbn_10("030640615"))

    def test_invalid_isbn_10_too_long(self):
        """ISBN-10 with more than 10 digits should fail."""
        self.assertFalse(_validate_isbn_10("03064061521"))

    def test_invalid_isbn_10_with_letters(self):
        """ISBN-10 with invalid characters should fail."""
        self.assertFalse(_validate_isbn_10("030640A152"))

    def test_valid_isbn_13_starting_with_978(self):
        """Valid ISBN-13 starting with 978 should pass."""
        self.assertTrue(_validate_isbn_13("9780306406157"))

    def test_valid_isbn_13_starting_with_979(self):
        """Valid ISBN-13 starting with 979 should pass."""
        self.assertTrue(_validate_isbn_13("9791234567896"))

    def test_invalid_isbn_13_wrong_checksum(self):
        """ISBN-13 with wrong checksum should fail."""
        self.assertFalse(_validate_isbn_13("9780306406158"))  # Last digit wrong

    def test_invalid_isbn_13_wrong_prefix(self):
        """ISBN-13 not starting with 978 or 979 should fail."""
        self.assertFalse(_validate_isbn_13("9771234567890"))

    def test_invalid_isbn_13_too_short(self):
        """ISBN-13 with fewer than 13 digits should fail."""
        self.assertFalse(_validate_isbn_13("978030640615"))

    def test_invalid_isbn_13_too_long(self):
        """ISBN-13 with more than 13 digits should fail."""
        self.assertFalse(_validate_isbn_13("97803064061571"))

    def test_invalid_isbn_13_with_letters(self):
        """ISBN-13 with non-digit characters should fail."""
        self.assertFalse(_validate_isbn_13("978030640615X"))


class ISBNDetectionTests(TestCase):
    """Test ISBN detection in wikitext."""

    def test_no_isbns_in_text(self):
        """Text without ISBNs should return empty list."""
        text = "This is just normal text without any ISBNs."
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_valid_isbn_10_with_hyphens(self):
        """Valid ISBN-10 with hyphens should not be flagged."""
        text = "isbn: 0-306-40615-2"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_valid_isbn_10_with_spaces(self):
        """Valid ISBN-10 with spaces should not be flagged."""
        text = "isbn 0 306 40615 2"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_valid_isbn_10_no_separators(self):
        """Valid ISBN-10 without separators should not be flagged."""
        text = "ISBN:0306406152"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_valid_isbn_13_various_formats(self):
        """Valid ISBN-13 in various formats should not be flagged."""
        text1 = "ISBN: 978-0-306-40615-7"
        text2 = "isbn = 978 0 306 40615 7"
        text3 = "Isbn:9780306406157"
        self.assertEqual(_find_invalid_isbns(text1), [])
        self.assertEqual(_find_invalid_isbns(text2), [])
        self.assertEqual(_find_invalid_isbns(text3), [])

    def test_invalid_isbn_10_detected(self):
        """Invalid ISBN-10 should be detected."""
        text = "isbn: 0-306-40615-3"  # Wrong check digit
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)
        self.assertIn("0-306-40615-3", invalid[0])

    def test_invalid_isbn_13_detected(self):
        """Invalid ISBN-13 should be detected."""
        text = "ISBN: 978-0-306-40615-8"  # Wrong check digit
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)

    def test_isbn_too_short_detected(self):
        """ISBN with fewer than 10 digits should be detected as invalid."""
        text = "isbn: 123-456"
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)

    def test_isbn_too_long_detected(self):
        """ISBN with more than 13 digits should be detected as invalid."""
        text = "isbn: 12345678901234"
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)

    def test_multiple_valid_isbns(self):
        """Multiple valid ISBNs should not be flagged."""
        text = """
        First book: ISBN: 0-306-40615-2
        Second book: ISBN: 978-0-306-40615-7
        """
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_multiple_isbns_with_one_invalid(self):
        """Text with one invalid ISBN among valid ones should flag the invalid one."""
        text = """
        Valid: ISBN: 0-306-40615-2
        Invalid: ISBN: 978-0-306-40615-8
        """
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)

    def test_multiple_invalid_isbns(self):
        """Text with multiple invalid ISBNs should flag all of them."""
        text = """
        Invalid 1: ISBN: 0-306-40615-3
        Invalid 2: ISBN: 978-0-306-40615-8
        """
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 2)

    def test_case_insensitive_isbn_detection(self):
        """ISBN detection should be case-insensitive."""
        text1 = "ISBN: 0-306-40615-2"
        text2 = "isbn: 0-306-40615-2"
        text3 = "Isbn: 0-306-40615-2"
        self.assertEqual(_find_invalid_isbns(text1), [])
        self.assertEqual(_find_invalid_isbns(text2), [])
        self.assertEqual(_find_invalid_isbns(text3), [])

    def test_isbn_with_equals_sign(self):
        """ISBN with = separator should be detected."""
        text = "isbn = 0-306-40615-2"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_isbn_with_colon(self):
        """ISBN with : separator should be detected."""
        text = "isbn: 0-306-40615-2"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_isbn_no_separator(self):
        """ISBN without separator should be detected."""
        text = "isbn 0-306-40615-2"
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_real_world_wikipedia_citation(self):
        """Test with realistic Wikipedia citation format."""
        text = """
        {{cite book |last=Smith |first=John |title=Example Book
        |publisher=Example Press |year=2020 |isbn=978-0-306-40615-7}}
        """
        self.assertEqual(_find_invalid_isbns(text), [])

    def test_invalid_isbn_in_wikipedia_citation(self):
        """Test invalid ISBN in Wikipedia citation format."""
        text = """
        {{cite book |last=Smith |first=John |title=Fake Book
        |publisher=Fake Press |year=2020 |isbn=978-0-306-40615-8}}
        """
        invalid = _find_invalid_isbns(text)
        self.assertEqual(len(invalid), 1)

    def test_isbn_with_trailing_year(self):
        """Test that trailing years are not captured as part of ISBN."""
        text = "isbn: 978 0 306 40615 7 2020"
        invalid = _find_invalid_isbns(text)
        # Should recognize valid ISBN and not capture the year
        self.assertEqual(len(invalid), 0)

    def test_isbn_with_spaces_around_hyphens(self):
        """Test that ISBNs with spaces around hyphens are fully captured."""
        text = "isbn: 978 - 0 - 306 - 40615 - 7"
        invalid = _find_invalid_isbns(text)
        # Should recognize valid ISBN with spaces around hyphens
        self.assertEqual(len(invalid), 0)

    def test_isbn_followed_by_punctuation(self):
        """Test that ISBNs followed by punctuation are correctly detected."""
        # ISBN followed by comma
        text1 = "isbn: 9780306406157, 2020"
        self.assertEqual(_find_invalid_isbns(text1), [])

        # ISBN followed by period
        text2 = "isbn: 0-306-40615-2."
        self.assertEqual(_find_invalid_isbns(text2), [])

        # ISBN followed by semicolon
        text3 = "isbn: 978-0-306-40615-7; another book"
        self.assertEqual(_find_invalid_isbns(text3), [])

        # Invalid ISBN followed by comma
        text4 = "isbn: 9780306406158, 2020"
        invalid = _find_invalid_isbns(text4)
        self.assertEqual(len(invalid), 1)


class AutoreviewBlockedUserTests(TestCase):
    def setUp(self):
        """Clear the LRU cache before each test."""
        self.wiki = Wiki.objects.create(code="fi", family="wikipedia")
        was_user_blocked_after.cache_clear()
        # Patch checks that run before the one we are testing
        self.unapproval_patcher = patch(
            "reviews.autoreview.WikiClient.has_manual_unapproval", return_value=False
        )
        self.mock_unapproval = self.unapproval_patcher.start()
        self.addCleanup(self.unapproval_patcher.stop)

    @patch("reviews.services.pywikibot.Site")
    def test_blocked_user_not_auto_approved(self, mock_site):
        """Test that a user blocked after making an edit is NOT auto-approved."""
        # Mock the pywikibot.Site and logevents to return a block event
        mock_site_instance = MagicMock()
        mock_site.return_value = mock_site_instance
        mock_block_event = MagicMock()
        mock_block_event.action.return_value = "block"
        mock_site_instance.logevents.return_value = [mock_block_event]

        # A non-bot, non-autoreviewed user profile
        profile = EditorProfile.objects.create(
            wiki=self.wiki,
            username="BlockedUser",
            is_bot=False,
            is_former_bot=False,
            is_global_bot=False,
            is_former_global_bot=False,
            is_autoreviewed=False,
            is_autopatrolled=False,
        )

        revision = MagicMock()
        revision.user_name = "BlockedUser"
        revision.timestamp = datetime.fromisoformat("2024-01-15T10:00:00")
        revision.page.title = "Test Page"
        revision.revid = 123
        revision.page.wiki = self.wiki
        revision.superset_data = {}

        from reviews.services import WikiClient

        client = WikiClient(self.wiki)

        # Call the function under test
        result = autoreview._evaluate_revision(
            revision,
            client,
            profile,
            auto_groups={},
            blocking_categories={},
            redirect_aliases=[],
        )

        # Assert
        self.assertEqual(result["decision"].status, "blocked")
        self.assertEqual(result["decision"].reason, "User was blocked after making this edit.")

        # Check the sequence of tests
        self.assertEqual(result["tests"][0]["id"], "manual-unapproval")
        self.assertEqual(result["tests"][0]["status"], "ok")
        self.assertEqual(result["tests"][1]["id"], "bot-user")
        self.assertEqual(result["tests"][1]["status"], "not_ok")
        self.assertEqual(result["tests"][2]["id"], "blocked-user")
        self.assertEqual(result["tests"][2]["status"], "fail")

        # Verify pywikibot.Site was called
        self.assertGreaterEqual(mock_site.call_count, 1)
        # Verify logevents was called with correct parameters
        mock_site_instance.logevents.assert_called_once()
