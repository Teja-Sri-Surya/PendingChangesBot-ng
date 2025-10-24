"""
Django management command to test approval comment generation.

This command allows testing the approval comment generation functionality
with various autoreview result scenarios.
"""

from django.core.management.base import BaseCommand, CommandError
from reviews.utils.approval_comment import generate_approval_comment, preview_approval_comment
from reviews.utils.approval_processor import process_and_approve_revisions, preview_approval_comment as preview_processor


class Command(BaseCommand):
    help = 'Test approval comment generation functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['bot', 'ores', 'mixed', 'none', 'single'],
            default='mixed',
            help='Test scenario to run (default: mixed)'
        )
        parser.add_argument(
            '--preview-only',
            action='store_true',
            help='Only preview the comment without making actual approval'
        )
        parser.add_argument(
            '--comment-prefix',
            type=str,
            default='Autoreview: ',
            help='Prefix for the approval comment (default: "Autoreview: ")'
        )

    def handle(self, *args, **options):
        scenario = options['scenario']
        preview_only = options['preview_only']
        comment_prefix = options['comment_prefix']

        # Generate test data based on scenario
        test_data = self._generate_test_data(scenario)
        
        self.stdout.write(f"Testing scenario: {scenario}")
        self.stdout.write(f"Comment prefix: '{comment_prefix}'")
        self.stdout.write(f"Preview only: {preview_only}")
        self.stdout.write("")
        
        # Display test data
        self.stdout.write("Test autoreview results:")
        for result in test_data:
            self.stdout.write(f"  Rev {result['revid']}: {result['decision']['status']} - {result['decision']['reason']}")
        self.stdout.write("")
        
        try:
            if preview_only:
                # Test comment generation only
                highest_rev_id, comment = generate_approval_comment(test_data)
                
                if highest_rev_id is None:
                    self.stdout.write(self.style.WARNING("No revisions can be approved"))
                else:
                    full_comment = comment_prefix + comment
                    self.stdout.write(f"Highest approvable revision: {highest_rev_id}")
                    self.stdout.write(f"Generated comment: {full_comment}")
                    self.stdout.write(f"Comment length: {len(full_comment)} characters")
            else:
                # Test full processing
                result = process_and_approve_revisions(test_data, comment_prefix)
                
                if result["success"]:
                    self.stdout.write(self.style.SUCCESS(f"✅ Approval successful"))
                    self.stdout.write(f"Revision ID: {result['rev_id']}")
                    self.stdout.write(f"Comment: {result['comment']}")
                else:
                    self.stdout.write(self.style.ERROR(f"❌ Approval failed: {result.get('message', 'Unknown error')}"))
                
                # Display summary
                summary = result.get("summary", {})
                self.stdout.write(f"Summary: {summary['approved_count']}/{summary['total_revisions']} revisions approved")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
            raise CommandError(f"Failed to process approval comment: {str(e)}")
        
        self.stdout.write(self.style.SUCCESS("✅ Command completed successfully"))

    def _generate_test_data(self, scenario: str) -> list:
        """Generate test autoreview results based on scenario."""
        
        if scenario == 'bot':
            return [
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
                }
            ]
        
        elif scenario == 'ores':
            return [
                {
                    "revid": 12345,
                    "tests": [],
                    "decision": {
                        "status": "approve",
                        "label": "Would be auto-approved",
                        "reason": "ORES score goodfaith=0.53, damaging=0.251"
                    }
                },
                {
                    "revid": 12346,
                    "tests": [],
                    "decision": {
                        "status": "approve",
                        "label": "Would be auto-approved",
                        "reason": "ORES score goodfaith=0.61, damaging=0.198"
                    }
                }
            ]
        
        elif scenario == 'mixed':
            return [
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
        
        elif scenario == 'none':
            return [
                {
                    "revid": 12345,
                    "tests": [],
                    "decision": {
                        "status": "blocked",
                        "label": "Cannot be auto-approved",
                        "reason": "Revision was manually un-approved"
                    }
                },
                {
                    "revid": 12346,
                    "tests": [],
                    "decision": {
                        "status": "blocked",
                        "label": "Cannot be auto-approved",
                        "reason": "User is blocked"
                    }
                }
            ]
        
        elif scenario == 'single':
            return [
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
        
        else:
            return []
