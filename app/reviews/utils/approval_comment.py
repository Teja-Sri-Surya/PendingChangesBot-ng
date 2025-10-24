"""
Utility functions for generating consolidated approval comments.

This module provides functions to process autoreview results and generate
consolidated approval comments for multiple revisions.
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def generate_approval_comment(autoreview_results: List[Dict]) -> Tuple[Optional[int], str]:
    """
    Generate a consolidated approval comment for the highest approvable revision.
    
    Args:
        autoreview_results: Results from run_autoreview_for_page() containing
                          approval decisions for each pending revision
        
    Returns:
        Tuple of (highest_rev_id, consolidated_comment)
        Returns (None, "") if no revisions can be approved
    """
    if not autoreview_results:
        return None, ""
    
    # Filter only approved revisions
    approved_revisions = [
        result for result in autoreview_results
        if result.get("decision", {}).get("status") == "approve"
    ]
    
    if not approved_revisions:
        return None, ""
    
    # Find the highest (latest) revision ID that can be approved
    highest_rev_id = max(
        result["revid"] for result in approved_revisions
    )
    
    # Get all revisions up to and including the highest revision
    revisions_to_approve = [
        result for result in approved_revisions
        if result["revid"] <= highest_rev_id
    ]
    
    # Sort by revision ID for consistent ordering
    revisions_to_approve.sort(key=lambda x: x["revid"])
    
    # Generate consolidated comment
    comment = _build_consolidated_comment(revisions_to_approve)
    
    return highest_rev_id, comment


def _build_consolidated_comment(revisions: List[Dict]) -> str:
    """
    Build a consolidated comment from a list of approved revisions.
    
    Args:
        revisions: List of approved revision results
        
    Returns:
        Consolidated comment string
    """
    if not revisions:
        return ""
    
    # Group consecutive revisions with identical reasons
    grouped_revisions = _group_revisions_by_reason(revisions)
    
    # Build comment parts
    comment_parts = []
    
    for group in grouped_revisions:
        rev_ids = [str(rev["revid"]) for rev in group["revisions"]]
        reason = group["reason"]
        
        if len(rev_ids) == 1:
            comment_parts.append(f"rev_id {rev_ids[0]} approved because {reason}")
        else:
            rev_ids_str = ", ".join(rev_ids)
            comment_parts.append(f"rev_id {rev_ids_str} approved because {reason}")
    
    # Join all parts with commas
    return ", ".join(comment_parts) + "."


def _group_revisions_by_reason(revisions: List[Dict]) -> List[Dict]:
    """
    Group consecutive revisions with identical approval reasons.
    
    Args:
        revisions: List of approved revision results
        
    Returns:
        List of groups with revisions and their common reason
    """
    if not revisions:
        return []
    
    groups = []
    current_group = {
        "revisions": [revisions[0]],
        "reason": revisions[0]["decision"]["reason"]
    }
    
    for i in range(1, len(revisions)):
        current_rev = revisions[i]
        current_reason = current_rev["decision"]["reason"]
        
        # Check if this revision has the same reason as the current group
        if current_reason == current_group["reason"]:
            current_group["revisions"].append(current_rev)
        else:
            # Start a new group
            groups.append(current_group)
            current_group = {
                "revisions": [current_rev],
                "reason": current_reason
            }
    
    # Add the last group
    groups.append(current_group)
    
    return groups


def _extract_approval_reason(decision: Dict) -> str:
    """
    Extract a clean approval reason from a decision object.
    
    Args:
        decision: Decision dictionary from autoreview results
        
    Returns:
        Cleaned approval reason string
    """
    reason = decision.get("reason", "")
    
    # Clean up common reason patterns
    if "user was a bot" in reason.lower():
        return "user was a bot"
    elif "no content change" in reason.lower():
        return "no content change in last article"
    elif "user was auto-reviewed" in reason.lower():
        return "user was auto-reviewed"
    elif "ores" in reason.lower() or "goodfaith" in reason.lower() or "damaging" in reason.lower():
        return _extract_ores_reason(reason)
    elif "revert to previously reviewed content" in reason.lower():
        return "revert to previously reviewed content"
    else:
        return reason


def _extract_ores_reason(reason: str) -> str:
    """
    Extract ORES-specific reason from a decision reason.
    
    Args:
        reason: Original reason string
        
    Returns:
        Cleaned ORES reason
    """
    # Look for ORES score patterns
    import re
    
    # Extract goodfaith and damaging scores if present
    goodfaith_match = re.search(r'goodfaith[=:]\s*([0-9.]+)', reason, re.IGNORECASE)
    damaging_match = re.search(r'damaging[=:]\s*([0-9.]+)', reason, re.IGNORECASE)
    
    if goodfaith_match and damaging_match:
        goodfaith_score = goodfaith_match.group(1)
        damaging_score = damaging_match.group(1)
        return f"ORES score goodfaith={goodfaith_score}, damaging={damaging_score}"
    elif goodfaith_match:
        goodfaith_score = goodfaith_match.group(1)
        return f"ORES score goodfaith={goodfaith_score}"
    elif damaging_match:
        damaging_score = damaging_match.group(1)
        return f"ORES score damaging={damaging_score}"
    else:
        return "ORES score threshold met"


def validate_comment_length(comment: str, max_length: int = 500) -> str:
    """
    Validate and truncate comment if it exceeds maximum length.
    
    Args:
        comment: Comment string to validate
        max_length: Maximum allowed length (default: 500)
        
    Returns:
        Validated and potentially truncated comment
    """
    if len(comment) <= max_length:
        return comment
    
    # Truncate and add ellipsis
    truncated = comment[:max_length - 3] + "..."
    logger.warning(f"Comment truncated from {len(comment)} to {len(truncated)} characters")
    
    return truncated


def get_approval_summary(autoreview_results: List[Dict]) -> Dict:
    """
    Get a summary of approval decisions for debugging and logging.
    
    Args:
        autoreview_results: Results from run_autoreview_for_page()
        
    Returns:
        Summary dictionary with approval statistics
    """
    total_revisions = len(autoreview_results)
    approved_revisions = [
        result for result in autoreview_results
        if result.get("decision", {}).get("status") == "approve"
    ]
    blocked_revisions = [
        result for result in autoreview_results
        if result.get("decision", {}).get("status") == "blocked"
    ]
    
    return {
        "total_revisions": total_revisions,
        "approved_count": len(approved_revisions),
        "blocked_count": len(blocked_revisions),
        "approval_rate": len(approved_revisions) / total_revisions if total_revisions > 0 else 0,
        "highest_approved_revid": max(
            (result["revid"] for result in approved_revisions), default=None
        )
    }
