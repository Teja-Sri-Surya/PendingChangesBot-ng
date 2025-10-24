"""
Unit tests for approval comment generation functionality.

Tests the approval comment generation and processing functions.
"""

import unittest
from unittest.mock import Mock, patch
from django.test import TestCase

from reviews.utils.approval_comment import (
    generate_approval_comment,
    _build_consolidated_comment,
    _group_revisions_by_reason,
    _extract_approval_reason,
    _extract_ores_reason,
    validate_comment_length,
    get_approval_summary
)
from reviews.utils.approval_processor import (
    process_and_approve_revisions,
    preview_approval_comment,
    batch_process_pages,
    get_approval_statistics
)


class ApprovalCommentTests(TestCase):
    """Test cases for approval comment generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_autoreview_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was a bot"
                }
            },
            {
                "revid": 12346,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "No content change in last article"
                }
            },
            {
                "revid": 12347,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was auto-reviewed"
                }
            },
            {
                "revid": 12348,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was auto-reviewed"
                }
            },
            {
                "revid": 12349,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "ORES score goodfaith=0.53, damaging=0.251"
                }
            }
        ]

    def test_generate_approval_comment_success(self):
        """Test successful approval comment generation."""
        highest_rev_id, comment = generate_approval_comment(self.sample_autoreview_results)
        
        self.assertEqual(highest_rev_id, 12349)  # Highest revision ID
        self.assertIn("rev_id 12345 approved because user was a bot", comment)
        self.assertIn("rev_id 12346 approved because no content change in last article", comment)
        self.assertIn("rev_id 12347, 12348 approved because user was auto-reviewed", comment)
        self.assertIn("rev_id 12349 approved because ORES score goodfaith=0.53, damaging=0.251", comment)

    def test_generate_approval_comment_no_approvals(self):
        """Test handling when no revisions can be approved."""
        blocked_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "blocked",
                    "label": "Cannot be auto-approved",
                    "reason": "User is blocked"
                }
            }
        ]
        
        highest_rev_id, comment = generate_approval_comment(blocked_results)
        
        self.assertIsNone(highest_rev_id)
        self.assertEqual(comment, "")

    def test_generate_approval_comment_empty_results(self):
        """Test handling of empty results."""
        highest_rev_id, comment = generate_approval_comment([])
        
        self.assertIsNone(highest_rev_id)
        self.assertEqual(comment, "")

    def test_build_consolidated_comment(self):
        """Test consolidated comment building."""
        revisions = [
            {
                "revid": 12345,
                "decision": {"reason": "User was a bot"}
            },
            {
                "revid": 12346,
                "decision": {"reason": "User was a bot"}
            },
            {
                "revid": 12347,
                "decision": {"reason": "ORES score goodfaith=0.53"}
            }
        ]
        
        comment = _build_consolidated_comment(revisions)
        
        self.assertIn("rev_id 12345, 12346 approved because user was a bot", comment)
        self.assertIn("rev_id 12347 approved because ORES score goodfaith=0.53", comment)

    def test_group_revisions_by_reason(self):
        """Test grouping revisions by reason."""
        revisions = [
            {"revid": 12345, "decision": {"reason": "User was a bot"}},
            {"revid": 12346, "decision": {"reason": "User was a bot"}},
            {"revid": 12347, "decision": {"reason": "ORES score goodfaith=0.53"}},
            {"revid": 12348, "decision": {"reason": "ORES score goodfaith=0.53"}}
        ]
        
        groups = _group_revisions_by_reason(revisions)
        
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]["revisions"]), 2)  # Two bot revisions
        self.assertEqual(len(groups[1]["revisions"]), 2)  # Two ORES revisions
        self.assertEqual(groups[0]["reason"], "User was a bot")
        self.assertEqual(groups[1]["reason"], "ORES score goodfaith=0.53")

    def test_extract_approval_reason(self):
        """Test approval reason extraction."""
        # Test bot reason
        bot_decision = {"reason": "User was a bot"}
        self.assertEqual(_extract_approval_reason(bot_decision), "user was a bot")
        
        # Test ORES reason
        ores_decision = {"reason": "ORES score goodfaith=0.53, damaging=0.251"}
        self.assertEqual(_extract_approval_reason(ores_decision), "ORES score goodfaith=0.53, damaging=0.251")
        
        # Test revert reason
        revert_decision = {"reason": "Revert to previously reviewed content"}
        self.assertEqual(_extract_approval_reason(revert_decision), "revert to previously reviewed content")

    def test_extract_ores_reason(self):
        """Test ORES reason extraction."""
        # Test with both scores
        reason1 = "ORES score goodfaith=0.53, damaging=0.251"
        self.assertEqual(_extract_ores_reason(reason1), "ORES score goodfaith=0.53, damaging=0.251")
        
        # Test with only goodfaith
        reason2 = "ORES score goodfaith=0.61"
        self.assertEqual(_extract_ores_reason(reason2), "ORES score goodfaith=0.61")
        
        # Test with only damaging
        reason3 = "ORES score damaging=0.198"
        self.assertEqual(_extract_ores_reason(reason3), "ORES score damaging=0.198")

    def test_validate_comment_length(self):
        """Test comment length validation."""
        short_comment = "Short comment"
        self.assertEqual(validate_comment_length(short_comment), short_comment)
        
        long_comment = "x" * 600
        validated = validate_comment_length(long_comment, max_length=500)
        self.assertEqual(len(validated), 500)
        self.assertTrue(validated.endswith("..."))

    def test_get_approval_summary(self):
        """Test approval summary generation."""
        summary = get_approval_summary(self.sample_autoreview_results)
        
        self.assertEqual(summary["total_revisions"], 5)
        self.assertEqual(summary["approved_count"], 5)
        self.assertEqual(summary["blocked_count"], 0)
        self.assertEqual(summary["approval_rate"], 1.0)
        self.assertEqual(summary["highest_approved_revid"], 12349)


class ApprovalProcessorTests(TestCase):
    """Test cases for approval processing functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_autoreview_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was a bot"
                }
            },
            {
                "revid": 12346,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "ORES score goodfaith=0.53, damaging=0.251"
                }
            }
        ]

    @patch('reviews.utils.approval_processor.approve_revision')
    def test_process_and_approve_revisions_success(self, mock_approve):
        """Test successful processing and approval."""
        mock_approve.return_value = {
            "result": "success",
            "dry_run": False,
            "message": "Successfully approved revision 12346"
        }
        
        result = process_and_approve_revisions(self.sample_autoreview_results)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["rev_id"], 12346)
        self.assertIn("rev_id 12345 approved because user was a bot", result["comment"])
        self.assertIn("rev_id 12346 approved because ORES score goodfaith=0.53, damaging=0.251", result["comment"])
        
        # Verify approve_revision was called with correct parameters
        mock_approve.assert_called_once()
        call_args = mock_approve.call_args
        self.assertEqual(call_args[1]["revid"], 12346)
        self.assertIn("Autoreview:", call_args[1]["comment"])

    @patch('reviews.utils.approval_processor.approve_revision')
    def test_process_and_approve_revisions_failure(self, mock_approve):
        """Test handling of approval failure."""
        mock_approve.return_value = {
            "result": "error",
            "dry_run": False,
            "message": "Permission denied"
        }
        
        result = process_and_approve_revisions(self.sample_autoreview_results)
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_process_and_approve_revisions_no_approvals(self):
        """Test handling when no revisions can be approved."""
        blocked_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "blocked",
                    "label": "Cannot be auto-approved",
                    "reason": "User is blocked"
                }
            }
        ]
        
        result = process_and_approve_revisions(blocked_results)
        
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "No revisions can be approved")

    def test_preview_approval_comment(self):
        """Test preview functionality."""
        result = preview_approval_comment(self.sample_autoreview_results)
        
        self.assertTrue(result["can_approve"])
        self.assertEqual(result["rev_id"], 12346)
        self.assertIn("Autoreview:", result["comment"])
        self.assertIsInstance(result["comment_length"], int)

    def test_batch_process_pages(self):
        """Test batch processing of multiple pages."""
        autoreview_results_by_page = {
            "Page1": self.sample_autoreview_results,
            "Page2": [
                {
                    "revid": 12350,
                    "tests": [],
                    "decision": {
                        "status": "approve",
                        "label": "Would be auto-approved",
                        "reason": "User was a bot"
                    }
                }
            ]
        }
        
        with patch('reviews.utils.approval_processor.approve_revision') as mock_approve:
            mock_approve.return_value = {
                "result": "success",
                "dry_run": False,
                "message": "Successfully approved"
            }
            
            results = batch_process_pages(autoreview_results_by_page)
            
            self.assertEqual(len(results), 2)
            self.assertIn("Page1", results)
            self.assertIn("Page2", results)

    def test_get_approval_statistics(self):
        """Test approval statistics generation."""
        autoreview_results_by_page = {
            "Page1": self.sample_autoreview_results,
            "Page2": [
                {
                    "revid": 12350,
                    "tests": [],
                    "decision": {
                        "status": "blocked",
                        "label": "Cannot be auto-approved",
                        "reason": "User is blocked"
                    }
                }
            ]
        }
        
        stats = get_approval_statistics(autoreview_results_by_page)
        
        self.assertEqual(stats["total_pages"], 2)
        self.assertEqual(stats["pages_with_approvals"], 1)
        self.assertEqual(stats["total_revisions"], 3)
        self.assertEqual(stats["total_approved"], 2)
        self.assertEqual(stats["total_blocked"], 1)


class ApprovalCommentIntegrationTests(TestCase):
    """Integration tests for approval comment functionality."""

    def test_end_to_end_workflow(self):
        """Test complete workflow from autoreview results to approval."""
        # Simulate autoreview results
        autoreview_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was a bot"
                }
            },
            {
                "revid": 12346,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was a bot"
                }
            },
            {
                "revid": 12347,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "ORES score goodfaith=0.53, damaging=0.251"
                }
            }
        ]
        
        # Test comment generation
        highest_rev_id, comment = generate_approval_comment(autoreview_results)
        
        self.assertEqual(highest_rev_id, 12347)
        self.assertIn("rev_id 12345, 12346 approved because user was a bot", comment)
        self.assertIn("rev_id 12347 approved because ORES score goodfaith=0.53, damaging=0.251", comment)
        
        # Test comment validation
        full_comment = "Autoreview: " + comment
        validated_comment = validate_comment_length(full_comment)
        
        self.assertIn("Autoreview:", validated_comment)
        self.assertLessEqual(len(validated_comment), 500)

    def test_edge_case_single_approval(self):
        """Test edge case with single approval."""
        autoreview_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "approve",
                    "label": "Would be auto-approved",
                    "reason": "User was a bot"
                }
            }
        ]
        
        highest_rev_id, comment = generate_approval_comment(autoreview_results)
        
        self.assertEqual(highest_rev_id, 12345)
        self.assertEqual(comment, "rev_id 12345 approved because user was a bot.")

    def test_edge_case_no_approvals(self):
        """Test edge case with no approvals."""
        autoreview_results = [
            {
                "revid": 12345,
                "tests": [],
                "decision": {
                    "status": "blocked",
                    "label": "Cannot be auto-approved",
                    "reason": "User is blocked"
                }
            }
        ]
        
        highest_rev_id, comment = generate_approval_comment(autoreview_results)
        
        self.assertIsNone(highest_rev_id)
        self.assertEqual(comment, "")
