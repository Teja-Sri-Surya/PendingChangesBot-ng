from __future__ import annotations

import json
import logging
from http import HTTPStatus

import requests
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .autoreview import run_autoreview_for_page
from .models import EditorProfile, PendingPage, Wiki, WikiConfiguration
from .services import WikiClient

logger = logging.getLogger(__name__)
CACHE_TTL = 60 * 60 * 1


def index(request: HttpRequest) -> HttpResponse:
    """Render the Vue.js application shell."""

    wikis = Wiki.objects.all().order_by("code")
    if not wikis.exists():
        # All Wikipedias using FlaggedRevisions extension
        # Source: https://noc.wikimedia.org/conf/highlight.php?file=flaggedrevs.php
        default_wikis = (
            {
                "name": "Alemannic Wikipedia",
                "code": "als",
                "api_endpoint": "https://als.wikipedia.org/w/api.php",
            },
            {
                "name": "Arabic Wikipedia",
                "code": "ar",
                "api_endpoint": "https://ar.wikipedia.org/w/api.php",
            },
            {
                "name": "Belarusian Wikipedia",
                "code": "be",
                "api_endpoint": "https://be.wikipedia.org/w/api.php",
            },
            {
                "name": "Bengali Wikipedia",
                "code": "bn",
                "api_endpoint": "https://bn.wikipedia.org/w/api.php",
            },
            {
                "name": "Bosnian Wikipedia",
                "code": "bs",
                "api_endpoint": "https://bs.wikipedia.org/w/api.php",
            },
            {
                "name": "Chechen Wikipedia",
                "code": "ce",
                "api_endpoint": "https://ce.wikipedia.org/w/api.php",
            },
            {
                "name": "Central Kurdish Wikipedia",
                "code": "ckb",
                "api_endpoint": "https://ckb.wikipedia.org/w/api.php",
            },
            {
                "name": "German Wikipedia",
                "code": "de",
                "api_endpoint": "https://de.wikipedia.org/w/api.php",
            },
            {
                "name": "English Wikipedia",
                "code": "en",
                "api_endpoint": "https://en.wikipedia.org/w/api.php",
            },
            {
                "name": "Esperanto Wikipedia",
                "code": "eo",
                "api_endpoint": "https://eo.wikipedia.org/w/api.php",
            },
            {
                "name": "Persian Wikipedia",
                "code": "fa",
                "api_endpoint": "https://fa.wikipedia.org/w/api.php",
            },
            {
                "name": "Finnish Wikipedia",
                "code": "fi",
                "api_endpoint": "https://fi.wikipedia.org/w/api.php",
            },
            {
                "name": "Hindi Wikipedia",
                "code": "hi",
                "api_endpoint": "https://hi.wikipedia.org/w/api.php",
            },
            {
                "name": "Hungarian Wikipedia",
                "code": "hu",
                "api_endpoint": "https://hu.wikipedia.org/w/api.php",
            },
            {
                "name": "Interlingua Wikipedia",
                "code": "ia",
                "api_endpoint": "https://ia.wikipedia.org/w/api.php",
            },
            {
                "name": "Indonesian Wikipedia",
                "code": "id",
                "api_endpoint": "https://id.wikipedia.org/w/api.php",
            },
            {
                "name": "Georgian Wikipedia",
                "code": "ka",
                "api_endpoint": "https://ka.wikipedia.org/w/api.php",
            },
            {
                "name": "Polish Wikipedia",
                "code": "pl",
                "api_endpoint": "https://pl.wikipedia.org/w/api.php",
            },
            {
                "name": "Portuguese Wikipedia",
                "code": "pt",
                "api_endpoint": "https://pt.wikipedia.org/w/api.php",
            },
            {
                "name": "Russian Wikipedia",
                "code": "ru",
                "api_endpoint": "https://ru.wikipedia.org/w/api.php",
            },
            {
                "name": "Albanian Wikipedia",
                "code": "sq",
                "api_endpoint": "https://sq.wikipedia.org/w/api.php",
            },
            {
                "name": "Turkish Wikipedia",
                "code": "tr",
                "api_endpoint": "https://tr.wikipedia.org/w/api.php",
            },
            {
                "name": "Ukrainian Wikipedia",
                "code": "uk",
                "api_endpoint": "https://uk.wikipedia.org/w/api.php",
            },
            {
                "name": "Venetian Wikipedia",
                "code": "vec",
                "api_endpoint": "https://vec.wikipedia.org/w/api.php",
            },
        )
        for defaults in default_wikis:
            wiki, _ = Wiki.objects.get_or_create(
                code=defaults["code"],
                defaults={
                    "name": defaults["name"],
                    "api_endpoint": defaults["api_endpoint"],
                },
            )
            WikiConfiguration.objects.get_or_create(wiki=wiki)
        wikis = Wiki.objects.all().order_by("code")
    payload = []
    for wiki in wikis:
        configuration, _ = WikiConfiguration.objects.get_or_create(wiki=wiki)
        payload.append(
            {
                "id": wiki.id,
                "name": wiki.name,
                "code": wiki.code,
                "api_endpoint": wiki.api_endpoint,
                "configuration": {
                    "blocking_categories": configuration.blocking_categories,
                    "auto_approved_groups": configuration.auto_approved_groups,
                },
            }
        )
    return render(
        request,
        "reviews/index.html",
        {
            "initial_wikis": payload,
        },
    )


@require_GET
def api_wikis(request: HttpRequest) -> JsonResponse:
    payload = []
    for wiki in Wiki.objects.all().order_by("code"):
        configuration = getattr(wiki, "configuration", None)
        payload.append(
            {
                "id": wiki.id,
                "name": wiki.name,
                "code": wiki.code,
                "api_endpoint": wiki.api_endpoint,
                "configuration": {
                    "blocking_categories": (
                        configuration.blocking_categories if configuration else []
                    ),
                    "auto_approved_groups": (
                        configuration.auto_approved_groups if configuration else []
                    ),
                },
            }
        )
    return JsonResponse({"wikis": payload})


def _get_wiki(pk: int) -> Wiki:
    wiki = get_object_or_404(Wiki, pk=pk)
    WikiConfiguration.objects.get_or_create(wiki=wiki)
    return wiki


@csrf_exempt
@require_http_methods(["POST"])
def api_refresh(request: HttpRequest, pk: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    client = WikiClient(wiki)
    try:
        pages = client.refresh()
    except Exception as exc:  # pragma: no cover - network failures handled in UI
        logger.exception("Failed to refresh pending changes for %s", wiki.code)
        return JsonResponse(
            {"error": str(exc)},
            status=HTTPStatus.BAD_GATEWAY,
        )
    return JsonResponse({"pages": [page.pageid for page in pages]})


def _build_revision_payload(revisions, wiki):
    usernames: set[str] = {revision.user_name for revision in revisions if revision.user_name}
    profiles = {
        profile.username: profile
        for profile in EditorProfile.objects.filter(wiki=wiki, username__in=usernames)
    }

    payload: list[dict] = []
    for revision in revisions:
        if revision.page and revision.revid == revision.page.stable_revid:
            continue
        profile = profiles.get(revision.user_name)
        superset_data = revision.superset_data or {}
        user_groups = profile.usergroups if profile else superset_data.get("user_groups", [])
        if not user_groups:
            user_groups = []
        group_set = set(user_groups)
        revision_categories = list(revision.categories or [])
        if revision_categories:
            categories = revision_categories
        else:
            page_categories = revision.page.categories or []
            if isinstance(page_categories, list) and page_categories:
                categories = [str(category) for category in page_categories if category]
            else:
                superset_categories = superset_data.get("page_categories") or []
                if isinstance(superset_categories, list):
                    categories = [str(category) for category in superset_categories if category]
                else:
                    categories = []

        payload.append(
            {
                "revid": revision.revid,
                "parentid": revision.parentid,
                "timestamp": revision.timestamp.isoformat(),
                "age_seconds": int(revision.age_at_fetch.total_seconds()),
                "user_name": revision.user_name,
                "change_tags": revision.change_tags
                if revision.change_tags
                else superset_data.get("change_tags", []),
                "comment": revision.comment,
                "categories": categories,
                "sha1": revision.sha1,
                "editor_profile": {
                    "usergroups": user_groups,
                    "is_blocked": (
                        profile.is_blocked
                        if profile
                        else bool(superset_data.get("user_blocked", False))
                    ),
                    "is_bot": (
                        profile.is_bot
                        if profile
                        else ("bot" in group_set or bool(superset_data.get("rc_bot")))
                    ),
                    "is_autopatrolled": (
                        profile.is_autopatrolled if profile else ("autopatrolled" in group_set)
                    ),
                    "is_autoreviewed": (
                        profile.is_autoreviewed
                        if profile
                        else bool(
                            group_set
                            & {"autoreview", "autoreviewer", "editor", "reviewer", "sysop", "bot"}
                        )
                    ),
                },
            }
        )
    return payload


@require_GET
def api_pending(request: HttpRequest, pk: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    pages_payload = []
    for page in PendingPage.objects.filter(wiki=wiki).prefetch_related("revisions"):
        revisions_payload = _build_revision_payload(page.revisions.all(), wiki)
        pages_payload.append(
            {
                "pageid": page.pageid,
                "title": page.title,
                "pending_since": page.pending_since.isoformat() if page.pending_since else None,
                "stable_revid": page.stable_revid,
                "revisions": revisions_payload,
            }
        )
    return JsonResponse({"pages": pages_payload})


@require_GET
def api_page_revisions(request: HttpRequest, pk: int, pageid: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    page = get_object_or_404(
        PendingPage.objects.prefetch_related("revisions"),
        wiki=wiki,
        pageid=pageid,
    )
    revisions_payload = _build_revision_payload(page.revisions.all(), wiki)
    return JsonResponse(
        {
            "pageid": page.pageid,
            "revisions": revisions_payload,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_autoreview(request: HttpRequest, pk: int, pageid: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    page = get_object_or_404(
        PendingPage.objects.prefetch_related("revisions"),
        wiki=wiki,
        pageid=pageid,
    )
    results = run_autoreview_for_page(page)
    return JsonResponse(
        {
            "pageid": page.pageid,
            "title": page.title,
            "mode": "dry-run",
            "results": results,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_clear_cache(request: HttpRequest, pk: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    deleted_pages, _ = PendingPage.objects.filter(wiki=wiki).delete()
    return JsonResponse({"cleared": deleted_pages})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def api_configuration(request: HttpRequest, pk: int) -> JsonResponse:
    wiki = _get_wiki(pk)
    configuration = wiki.configuration
    if request.method == "PUT":
        if request.content_type == "application/json":
            payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        else:
            payload = request.POST.dict()
        blocking_categories = payload.get("blocking_categories", [])
        auto_groups = payload.get("auto_approved_groups", [])
        if isinstance(blocking_categories, str):
            blocking_categories = [blocking_categories]
        if isinstance(auto_groups, str):
            auto_groups = [auto_groups]
        configuration.blocking_categories = blocking_categories
        configuration.auto_approved_groups = auto_groups
        configuration.save(
            update_fields=["blocking_categories", "auto_approved_groups", "updated_at"]
        )
    return JsonResponse(
        {
            "blocking_categories": configuration.blocking_categories,
            "auto_approved_groups": configuration.auto_approved_groups,
        }
    )

def fetch_diff(request):
    url = request.GET.get("url")
    if not url:
        return JsonResponse(
            {
                "error": "Missing 'url' parameter"
            }, status=400)

    cached_html = cache.get(url)
    if cached_html:
        return HttpResponse(cached_html, content_type="text/html")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DiffFetcher/1.0; +https://yourdomain.com)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        html_content = response.text

        cache.set(url, html_content, CACHE_TTL)

        return HttpResponse(html_content, content_type="text/html")
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=500)


# LiftWing Model Visualization Views

def liftwing_page(request: HttpRequest) -> HttpResponse:
    """Render the LiftWing model visualization page."""
    return render(request, "reviews/lift.html")


@csrf_exempt
@require_http_methods(["POST"])
def validate_article(request: HttpRequest) -> JsonResponse:
    """Validate that an article exists on the specified wiki."""
    try:
        data = json.loads(request.body)
        wiki_code = data.get("wiki", "en")
        article_title = data.get("title", "")
        
        if not article_title:
            return JsonResponse({"error": "Article title is required"}, status=400)
        
        # Use MediaWiki API to validate article existence
        api_url = f"https://{wiki_code}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": article_title,
            "prop": "info",
            "inprop": "url"
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        
        # Check if article exists (not -1 means it exists)
        for page_id, page_info in pages.items():
            if page_id != "-1":  # Article exists
                return JsonResponse({
                    "exists": True,
                    "title": page_info.get("title", article_title),
                    "pageid": int(page_id),
                    "url": page_info.get("fullurl", "")
                })
        
        return JsonResponse({
            "exists": False,
            "title": article_title,
            "error": "Article not found"
        })
        
    except Exception as e:
        logger.error(f"Error validating article: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def fetch_revisions(request: HttpRequest) -> JsonResponse:
    """Fetch revision history for an article."""
    try:
        data = json.loads(request.body)
        wiki_code = data.get("wiki", "en")
        article_title = data.get("title", "")
        limit = data.get("limit", 50)
        
        if not article_title:
            return JsonResponse({"error": "Article title is required"}, status=400)
        
        # Use MediaWiki API to fetch revision history
        api_url = f"https://{wiki_code}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": article_title,
            "prop": "revisions",
            "rvprop": "ids|timestamp|user|comment|size|sha1",
            "rvlimit": limit,
            "rvdir": "newer"  # Get revisions from oldest to newest
        }
        
        response = requests.get(api_url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        
        revisions = []
        for page_id, page_info in pages.items():
            if page_id != "-1":
                revs = page_info.get("revisions", [])
                for rev in revs:
                    revisions.append({
                        "revid": rev.get("revid"),
                        "timestamp": rev.get("timestamp"),
                        "user": rev.get("user", "Anonymous"),
                        "comment": rev.get("comment", ""),
                        "size": rev.get("size", 0),
                        "sha1": rev.get("sha1", "")
                    })
        
        return JsonResponse({
            "revisions": revisions,
            "total": len(revisions)
        })
        
    except Exception as e:
        logger.error(f"Error fetching revisions: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def fetch_predictions(request: HttpRequest) -> JsonResponse:
    """Fetch predictions for a single revision."""
    try:
        data = json.loads(request.body)
        wiki_code = data.get("wiki", "en")
        model = data.get("model", "articlequality")
        rev_id = data.get("rev_id")
        
        if not rev_id:
            return JsonResponse({"error": "Revision ID is required"}, status=400)
        
        # Use LiftWing API to get prediction
        url = f"https://api.wikimedia.org/service/lw/inference/v1/models/{wiki_code}wiki-{model}/predict"
        headers = {"User-Agent": "PendingChangesBot/1.0"}
        payload = {"rev_id": rev_id}
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        result = response.json()
        return JsonResponse({
            "rev_id": rev_id,
            "prediction": result.get("output", result)
        })
        
    except Exception as e:
        logger.error(f"Error fetching prediction: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def fetch_liftwing_predictions(request: HttpRequest) -> JsonResponse:
    """Fetch predictions for multiple revisions using parallel requests."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    try:
        data = json.loads(request.body)
        wiki_code = data.get("wiki", "en")
        model = data.get("model", "articlequality")
        revisions = data.get("revisions", [])
        
        if not revisions:
            return JsonResponse({"error": "Revisions list is required"}, status=400)
        
        # Base URL for LiftWing API
        base_url = f"https://api.wikimedia.org/service/lw/inference/v1/models/{wiki_code}wiki-{model}/predict"
        headers = {"User-Agent": "PendingChangesBot/1.0"}
        
        def fetch_single_prediction(rev_id):
            """Fetch prediction for a single revision ID"""
            try:
                payload = {"rev_id": rev_id}
                response = requests.post(base_url, json=payload, headers=headers, timeout=15)
                response.raise_for_status()
                result = response.json()
                return (rev_id, result.get("output", result))
            except requests.exceptions.Timeout:
                return (rev_id, {"error": "Request timed out"})
            except requests.exceptions.HTTPError as e:
                return (rev_id, {"error": f"HTTP {e.response.status_code}: {str(e)}"})
            except Exception as e:
                return (rev_id, {"error": str(e)})
        
        predictions = {}
        
        # Use ThreadPoolExecutor for parallel requests (max 10 concurrent)
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_rev = {executor.submit(fetch_single_prediction, rev_id): rev_id 
                            for rev_id in revisions}
            
            # Collect results as they complete
            for future in as_completed(future_to_rev):
                rev_id, prediction = future.result()
                predictions[rev_id] = prediction
        
        return JsonResponse({"predictions": predictions})
        
    except Exception as e:
        logger.error(f"Error fetching LiftWing predictions: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@require_GET
def liftwing_models(request: HttpRequest, wiki_code: str) -> JsonResponse:
    """Return available LiftWing models for the given wiki."""
    # Comprehensive list of available Wikimedia ML models
    models = [
        {
            "name": "articlequality",
            "version": "1.0.0",
            "description": "Predicts the quality class of Wikipedia articles",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        },
        {
            "name": "draftquality",
            "version": "1.0.0",
            "description": "Predicts the quality of new article drafts",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        },
        {
            "name": "revertrisk",
            "version": "1.0.0",
            "description": "Predicts the likelihood of an edit being reverted",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        },
        {
            "name": "revertrisk-multilingual",
            "version": "1.0.0",
            "description": "Multilingual revert risk prediction",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        },
        {
            "name": "damaging",
            "version": "1.0.0",
            "description": "Predicts if an edit is damaging",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        },
        {
            "name": "goodfaith",
            "version": "1.0.0",
            "description": "Predicts if an edit is made in good faith",
            "supported_languages": ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "zh", "ar", "hi", "tr", "pl", "nl", "sv", "no", "da", "fi", "cs", "hu", "ro", "bg", "hr", "sk", "sl", "et", "lv", "lt", "el", "he", "th", "vi", "ko", "uk", "be", "mk", "sq", "sr", "bs", "hr", "sl", "sk", "cs", "pl", "hu", "ro", "bg", "el", "tr", "ar", "he", "fa", "ur", "hi", "bn", "ta", "te", "ml", "kn", "gu", "pa", "or", "as", "ne", "si", "my", "km", "lo", "th", "vi", "ko", "ja", "zh", "yue", "zh-min-nan", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical", "zh-yue", "yue", "nan", "hak", "gan", "wuu", "cdo", "mnp", "cjy", "hsn", "lzh", "zh-classical"]
        }
    ]
    
    # Filter models that support the given wiki language
    supported_models = [
        model for model in models 
        if wiki_code in model["supported_languages"]
    ]
    
    return JsonResponse({"models": supported_models})
