"""Tests for domain verification functionality."""

import re
from unittest.mock import MagicMock

from django.test import TestCase

from reviews.autoreview import _check_domain_verification, _extract_domain_from_url, _is_valid_domain
from reviews.models import PendingPage, PendingRevision, Wiki


class DomainVerificationTest(TestCase):
    def setUp(self):
        """Set up test data."""
        self.wiki = Wiki.objects.create(name="Test Wiki", code="test", family="wikipedia")
        self.page = PendingPage.objects.create(
            wiki=self.wiki,
            pageid=123,
            title="Test Page",
            stable_revid=100,
        )
        self.client = MagicMock()

    def test_extract_domain_from_url(self):
        """Test domain extraction from URLs."""
        # Valid URLs
        self.assertEqual(_extract_domain_from_url("https://example.com"), "example.com")
        self.assertEqual(_extract_domain_from_url("http://test.org/path"), "test.org")
        self.assertEqual(_extract_domain_from_url("https://subdomain.example.com:8080"), "subdomain.example.com")
        
        # URLs with ports
        self.assertEqual(_extract_domain_from_url("https://example.com:443"), "example.com")
        self.assertEqual(_extract_domain_from_url("http://localhost:3000"), "localhost")
        
        # Invalid URLs
        self.assertEqual(_extract_domain_from_url(""), "")
        self.assertEqual(_extract_domain_from_url("not-a-url"), "")

    def test_is_valid_domain(self):
        """Test domain validation logic."""
        # Valid domains
        self.assertTrue(_is_valid_domain("example.com"))
        self.assertTrue(_is_valid_domain("test.org"))
        self.assertTrue(_is_valid_domain("subdomain.example.com"))
        self.assertTrue(_is_valid_domain("wikipedia.org"))
        
        # Invalid domains
        self.assertFalse(_is_valid_domain(""))
        self.assertFalse(_is_valid_domain("ab"))  # Too short
        self.assertFalse(_is_valid_domain("example"))  # No TLD
        self.assertFalse(_is_valid_domain("example.c"))  # TLD too short
        
        # Blacklisted domains
        self.assertFalse(_is_valid_domain("localhost"))
        self.assertFalse(_is_valid_domain("127.0.0.1"))
        self.assertFalse(_is_valid_domain("example.com"))
        self.assertFalse(_is_valid_domain("test.com"))
        
        # Suspicious patterns
        self.assertFalse(_is_valid_domain("192.168.1.1"))  # IP address
        self.assertFalse(_is_valid_domain("example..com"))  # Multiple dots
        self.assertFalse(_is_valid_domain("example@com"))  # Invalid characters

    def test_domain_verification_no_new_links(self):
        """Test domain verification when no new links are added."""
        revision = PendingRevision.objects.create(
            page=self.page,
            revid=101,
            wikitext="Some text with https://example.com",
            user_name="TestUser",
            sha1="testsha1",
        )
        
        # Mock parent wikitext to be the same
        with self.assertLogs('reviews.autoreview', level='DEBUG') as cm:
            result = _check_domain_verification(revision, self.client)
        
        self.assertEqual(result["status"], "ok")
        self.assertIn("No new external links added", result["message"])

    def test_domain_verification_valid_links(self):
        """Test domain verification with valid new links."""
        revision = PendingRevision.objects.create(
            page=self.page,
            revid=101,
            wikitext="Some text with https://wikipedia.org and http://example.org",
            user_name="TestUser",
            sha1="testsha1",
        )
        
        # Mock parent wikitext to have no links
        with self.assertLogs('reviews.autoreview', level='DEBUG') as cm:
            result = _check_domain_verification(revision, self.client)
        
        self.assertEqual(result["status"], "ok")
        self.assertIn("All 2 new external links have valid domains", result["message"])

    def test_domain_verification_invalid_links(self):
        """Test domain verification with invalid links."""
        revision = PendingRevision.objects.create(
            page=self.page,
            revid=101,
            wikitext="Some text with https://localhost and http://192.168.1.1",
            user_name="TestUser",
            sha1="testsha1",
        )
        
        # Mock parent wikitext to have no links
        with self.assertLogs('reviews.autoreview', level='DEBUG') as cm:
            result = _check_domain_verification(revision, self.client)
        
        self.assertEqual(result["status"], "manual")
        self.assertIn("New external links with potentially invalid domains", result["message"])
        self.assertIn("invalid_urls", result["details"])
        self.assertEqual(len(result["details"]["invalid_urls"]), 2)

    def test_domain_verification_mixed_links(self):
        """Test domain verification with mix of valid and invalid links."""
        revision = PendingRevision.objects.create(
            page=self.page,
            revid=101,
            wikitext="Valid: https://wikipedia.org, Invalid: https://localhost",
            user_name="TestUser",
            sha1="testsha1",
        )
        
        # Mock parent wikitext to have no links
        with self.assertLogs('reviews.autoreview', level='DEBUG') as cm:
            result = _check_domain_verification(revision, self.client)
        
        self.assertEqual(result["status"], "manual")
        self.assertIn("New external links with potentially invalid domains", result["message"])
        self.assertIn("https://localhost", result["message"])

    def test_domain_verification_error_handling(self):
        """Test domain verification error handling."""
        revision = PendingRevision.objects.create(
            page=self.page,
            revid=101,
            wikitext="Some text",
            user_name="TestUser",
            sha1="testsha1",
        )
        
        # Mock client to raise an exception
        self.client.side_effect = Exception("Test error")
        
        with self.assertLogs('reviews.autoreview', level='ERROR') as cm:
            result = _check_domain_verification(revision, self.client)
        
        self.assertEqual(result["status"], "error")
        self.assertIn("Domain verification check failed", result["message"])

    def test_url_pattern_matching(self):
        """Test URL pattern matching in wikitext."""
        test_cases = [
            ("https://example.com", ["https://example.com"]),
            ("http://test.org/path", ["http://test.org/path"]),
            ("Multiple https://first.com and http://second.org links", 
             ["https://first.com", "http://second.org"]),
            ("No links here", []),
            ("[https://example.com](link)", ["https://example.com"]),
        ]
        
        for wikitext, expected_urls in test_cases:
            with self.subTest(wikitext=wikitext):
                urls = re.findall(r'https?://[^\s\[\]{}|`<>"]+', wikitext, re.IGNORECASE)
                self.assertEqual(set(urls), set(expected_urls))
