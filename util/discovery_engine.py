"""

Created on Jan. 26 by Jon Hogg
Last modified Feb. 18, 2026
"""

from typing import Dict, List, Optional, Tuple
import logging
import requests
from constants import (
    DISCOVERY_ENGINE_PROJECT_ID,
    DISCOVERY_ENGINE_LOCATION,
    DISCOVERY_ENGINE_COLLECTION,
    DISCOVERY_ENGINE_SERVING_CONFIG,
    DISCOVERY_ENGINE_ENGINE_ID,
)

from util.google_analytics import send_ga4_event
from constants import IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID

logger = logging.getLogger(__name__)


API_VERSION = "v1alpha"


def _serving_config() -> str:
    """
    Build the Discovery Engine serving config resource path.
    Raises if required Discovery Engine env vars are missing.
    """
    missing = []
    if not DISCOVERY_ENGINE_PROJECT_ID:
        missing.append("DISCOVERY_ENGINE_PROJECT_ID")
    if not DISCOVERY_ENGINE_LOCATION:
        missing.append("DISCOVERY_ENGINE_LOCATION")
    if not DISCOVERY_ENGINE_COLLECTION:
        missing.append("DISCOVERY_ENGINE_COLLECTION")
    if not DISCOVERY_ENGINE_SERVING_CONFIG:
        missing.append("DISCOVERY_ENGINE_SERVING_CONFIG")
    if not DISCOVERY_ENGINE_ENGINE_ID:
        missing.append("DISCOVERY_ENGINE_ENGINE_ID")

    if missing:
        raise ValueError(f"Missing Discovery Engine env vars: {', '.join(missing)}")

    return (
        "projects/"
        f"{DISCOVERY_ENGINE_PROJECT_ID}/"
        "locations/"
        f"{DISCOVERY_ENGINE_LOCATION}/"
        "collections/"
        f"{DISCOVERY_ENGINE_COLLECTION}/"
        "engines/"
        f"{DISCOVERY_ENGINE_ENGINE_ID}/"
        "servingConfigs/"
        f"{DISCOVERY_ENGINE_SERVING_CONFIG}"
    )


def _session_path() -> str:
    """
    Build the Discovery Engine session resource path.
    Uses an ephemeral session id placeholder.
    """
    return (
        "projects/"
        f"{DISCOVERY_ENGINE_PROJECT_ID}/"
        "locations/"
        f"{DISCOVERY_ENGINE_LOCATION}/"
        "collections/"
        f"{DISCOVERY_ENGINE_COLLECTION}/"
        "engines/"
        f"{DISCOVERY_ENGINE_ENGINE_ID}/"
        "sessions/-"
    )


def answer_query(
    query: str,
    access_token: str,
    user_pseudo_id: Optional[str] = None,
) -> dict:
    """
    Call the Discovery Engine answer endpoint for a question.
    Returns the parsed JSON response or raises on API errors.
    """
    send_ga4_event(
        name="scout_query",
        measurement_id=IMC_CONSOLE_GOOGLE_ANALYTICS_MEASUREMENT_ID,
        params={"utm_source": "Slack"},
        client_id=user_pseudo_id,
    )

    serving_config = _serving_config()
    url = (
        f"https://discoveryengine.googleapis.com/{API_VERSION}/{serving_config}:answer"
    )
    logging.debug(f"[discovery_engine] POST {url}")
    body = {
        "query": {"text": query},
        "session": _session_path(),
        "answerGenerationSpec": {
            "includeCitations": True,
            "ignoreAdversarialQuery": True,
            "ignoreNonAnswerSeekingQuery": False,
            "ignoreLowRelevantContent": True,
            "modelSpec": {"modelVersion": "stable"},
        },
    }
    if user_pseudo_id:
        body["userPseudoId"] = user_pseudo_id

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if DISCOVERY_ENGINE_PROJECT_ID:
        headers["x-goog-user-project"] = DISCOVERY_ENGINE_PROJECT_ID

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    logging.debug(
        f"[discovery_engine] status={resp.status_code} body={resp.text[:2000]}"
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Discovery Engine error {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def search_query(
    query: str,
    access_token: str,
    user_pseudo_id: Optional[str] = None,
    page_size: int = 10,
) -> dict:
    """
    Call the Discovery Engine search endpoint for source retrieval.
    Returns the parsed JSON response or raises on API errors.
    """
    serving_config = _serving_config()
    url = (
        f"https://discoveryengine.googleapis.com/{API_VERSION}/{serving_config}:search"
    )
    logging.debug(f"[discovery_engine] POST {url}")
    body = {
        "query": query,
        "pageSize": page_size,
        "queryExpansionSpec": {"condition": "AUTO"},
        "spellCorrectionSpec": {"mode": "AUTO"},
        "languageCode": "en-US",
        "contentSearchSpec": {"extractiveContentSpec": {"maxExtractiveAnswerCount": 1}},
        "userInfo": {"timeZone": "America/Chicago"},
        "session": _session_path(),
    }
    if user_pseudo_id:
        body["userPseudoId"] = user_pseudo_id

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if DISCOVERY_ENGINE_PROJECT_ID:
        headers["x-goog-user-project"] = DISCOVERY_ENGINE_PROJECT_ID

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    logging.debug(
        f"[discovery_engine] status={resp.status_code} body={resp.text[:2000]}"
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Discovery Engine error {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def extract_search_results(response: dict) -> List[Dict]:
    """
    Extract source title/URI pairs from a search API response.
    Filters out results that have neither a title nor URI.
    """
    results = response.get("results") or []
    out: List[Dict] = []
    for res in results:
        doc = res.get("document") or {}
        derived = doc.get("derivedStructData") or {}
        title = derived.get("title")
        uri = derived.get("link") or derived.get("uri") or derived.get("document")
        if not title:
            title = uri
        if title or uri:
            out.append({"title": title, "uri": uri})
    return out


def _get_ref_id(ref: dict, index: int) -> str:
    """
    Resolve a stable reference id from varying API field names.
    Falls back to the reference index when no id fields exist.
    """
    return (
        ref.get("referenceId")
        or ref.get("reference_id")
        or ref.get("name")
        or str(index)
    )


def _get_doc_metadata(ref: dict) -> dict:
    """
    Extract document metadata from a citation reference object.
    Checks structured, chunked, then unstructured payload shapes.
    """
    # 1. Check for Structured Info (Priority for Google Drive results)
    structured = ref.get("structuredDocumentInfo") or ref.get(
        "structured_document_info"
    )
    if structured:
        return structured

    # 2. Check for Chunk Info (Standard for unstructured data)
    chunk_info = ref.get("chunkInfo") or ref.get("chunk_info") or {}
    doc_meta = (
        chunk_info.get("documentMetadata") or chunk_info.get("document_metadata") or {}
    )
    if doc_meta:
        return doc_meta

    # 3. Check for Unstructured Info (General fallback)
    unstructured = (
        ref.get("unstructuredDocumentInfo")
        or ref.get("unstructured_document_info")
        or {}
    )
    doc_meta = (
        unstructured.get("documentMetadata")
        or unstructured.get("document_metadata")
        or {}
    )

    #    if doc_meta:
    #         return doc_meta

    #     structured = (
    #         ref.get("structuredDocumentInfo") or ref.get("structured_document_info") or {}
    #     )
    #     doc_meta = (
    #         structured.get("documentMetadata") or structured.get("document_metadata") or {}
    #     )

    return doc_meta or {}


def _extract_title_uri(ref: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Derive a display title and URI from reference metadata.
    Uses URI as a fallback title when no title is present.
    """
    doc_meta = _get_doc_metadata(ref)
    title = doc_meta.get("title")
    uri = doc_meta.get("uri") or doc_meta.get("document")
    if not title:
        title = uri
    return title, uri


def extract_answer_and_citations(
    response: dict,
) -> Tuple[Optional[str], List[Dict], List]:
    """
    Parse answer text, sources, and skipped reasons from API output.
    Prefers citation-linked sources and falls back to top references.
    """
    answer = response.get("answer") or {}
    answer_text = (
        answer.get("answerText")
        or answer.get("answer_text")
        or answer.get("text")
        or answer.get("answer")
    )
    skipped_reasons = (
        answer.get("answerSkippedReasons") or answer.get("answer_skipped_reasons") or []
    )

    references = answer.get("references") or []
    ref_map = {}
    for idx, ref in enumerate(references):
        ref_id = _get_ref_id(ref, idx)
        title, uri = _extract_title_uri(ref)
        ref_map[ref_id] = {"title": title, "uri": uri}

    citation_refs: List[str] = []
    citations = answer.get("citations") or []
    for citation in citations:
        sources = citation.get("sources") or []
        for source in sources:
            ref_id = source.get("referenceId") or source.get("reference_id")
            if ref_id:
                citation_refs.append(ref_id)

    seen = set()
    sources_out: List[Dict] = []
    for ref_id in citation_refs:
        if ref_id in seen:
            continue
        seen.add(ref_id)
        ref = ref_map.get(ref_id)
        if ref:
            sources_out.append(ref)

    if not sources_out and ref_map:
        for _, ref in ref_map.items():
            sources_out.append(ref)
            if len(sources_out) >= 5:
                break

    return answer_text, sources_out, skipped_reasons
