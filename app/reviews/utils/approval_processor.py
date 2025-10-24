"""
Integration functions for processing autoreview results and making approvals.

This module provides high-level functions that combine autoreview processing
with approval comment generation and actual approval actions.
"""

import logging
from typing import Dict, List, Tuple, Optional

from .approval import approve_revision
from .approval_comment import generate_approval_comment, validate_comment_length, get_approval_summary

logger = logging.getLogger(__name__)


def process_and_approve_revisions(autoreview_results: List[Dict], 
                                 comment_prefix: str = "Autoreview: ") -> Dict:
    """
    Process autoreview results and approve the highest approvable revision.
    
    Args:
        autoreview_results: Results from run_autoreview_for_page()
        comment_prefix: Prefix to add to the generated comment
        
    Returns:
        Dictionary with approval result and metadata
    """
    try:
        # Generate consolidated approval comment
        highest_rev_id, comment = generate_approval_comment(autoreview_results)
        
        if highest_rev_id is None:
            return {
                "success": False,
                "message": "No revisions can be approved",
                "summary": get_approval_summary(autoreview_results)
            }
        
        # Validate comment length
        full_comment = comment_prefix + comment
        validated_comment = validate_comment_length(full_comment)
        
        # Make the approval
        approval_result = approve_revision(
            revid=highest_rev_id,
            comment=validated_comment,
            unapprove=False
        )
        
        return {
            "success": approval_result["result"] == "success",
            "rev_id": highest_rev_id,
            "comment": validated_comment,
            "approval_result": approval_result,
            "summary": get_approval_summary(autoreview_results)
        }
        
    except Exception as e:
        logger.error(f"Error processing and approving revisions: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "summary": get_approval_summary(autoreview_results)
        }


def preview_approval_comment(autoreview_results: List[Dict], 
                           comment_prefix: str = "Autoreview: ") -> Dict:
    """
    Preview what the approval comment would look like without making actual approval.
    
    Args:
        autoreview_results: Results from run_autoreview_for_page()
        comment_prefix: Prefix to add to the generated comment
        
    Returns:
        Dictionary with preview information
    """
    try:
        # Generate consolidated approval comment
        highest_rev_id, comment = generate_approval_comment(autoreview_results)
        
        if highest_rev_id is None:
            return {
                "can_approve": False,
                "message": "No revisions can be approved",
                "summary": get_approval_summary(autoreview_results)
            }
        
        # Validate comment length
        full_comment = comment_prefix + comment
        validated_comment = validate_comment_length(full_comment)
        
        return {
            "can_approve": True,
            "rev_id": highest_rev_id,
            "comment": validated_comment,
            "comment_length": len(validated_comment),
            "summary": get_approval_summary(autoreview_results)
        }
        
    except Exception as e:
        logger.error(f"Error previewing approval comment: {str(e)}")
        return {
            "can_approve": False,
            "error": str(e),
            "summary": get_approval_summary(autoreview_results)
        }


def batch_process_pages(autoreview_results_by_page: Dict[str, List[Dict]], 
                       comment_prefix: str = "Autoreview: ") -> Dict:
    """
    Process multiple pages and their autoreview results.
    
    Args:
        autoreview_results_by_page: Dictionary mapping page titles to autoreview results
        comment_prefix: Prefix to add to the generated comment
        
    Returns:
        Dictionary with results for each page
    """
    results = {}
    
    for page_title, autoreview_results in autoreview_results_by_page.items():
        try:
            page_result = process_and_approve_revisions(
                autoreview_results, comment_prefix
            )
            results[page_title] = page_result
        except Exception as e:
            logger.error(f"Error processing page {page_title}: {str(e)}")
            results[page_title] = {
                "success": False,
                "error": str(e),
                "summary": get_approval_summary(autoreview_results)
            }
    
    return results


def get_approval_statistics(autoreview_results_by_page: Dict[str, List[Dict]]) -> Dict:
    """
    Get statistics about approval decisions across multiple pages.
    
    Args:
        autoreview_results_by_page: Dictionary mapping page titles to autoreview results
        
    Returns:
        Dictionary with aggregated statistics
    """
    total_pages = len(autoreview_results_by_page)
    pages_with_approvals = 0
    total_revisions = 0
    total_approved = 0
    total_blocked = 0
    
    for page_title, autoreview_results in autoreview_results_by_page.items():
        summary = get_approval_summary(autoreview_results)
        
        total_revisions += summary["total_revisions"]
        total_approved += summary["approved_count"]
        total_blocked += summary["blocked_count"]
        
        if summary["approved_count"] > 0:
            pages_with_approvals += 1
    
    return {
        "total_pages": total_pages,
        "pages_with_approvals": pages_with_approvals,
        "total_revisions": total_revisions,
        "total_approved": total_approved,
        "total_blocked": total_blocked,
        "overall_approval_rate": total_approved / total_revisions if total_revisions > 0 else 0,
        "pages_approval_rate": pages_with_approvals / total_pages if total_pages > 0 else 0
    }
