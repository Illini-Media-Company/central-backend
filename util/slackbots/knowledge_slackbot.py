"""

Created on Jan. 26 by Jon Hogg
Last modified Feb. 18, 2026
"""

import datetime
import re
import random
from util.slackbots._slackbot import app
from threading import Thread
from util.security import csrf
from db.user import add_user, get_user_entity, check_and_log_query
from util.ask_oauth import get_valid_access_token
from util.discovery_engine import (
    answer_query,
    extract_answer_and_citations,
    extract_search_results,
    search_query,
)
from constants import PUBLIC_BASE_URL, SLACK_BOT_TOKEN


def _slack_user_profile(user_id):
    """
    Fetch a Slack user's profile data by user id.
    Returns None if the Slack API call fails.
    """
    try:
        res = app.client.users_info(token=SLACK_BOT_TOKEN, user=user_id)
        return res.get("user", {}).get("profile", {})
    except Exception as e:
        print(f"[ask] users_info failed: {e}")
        return None


def _format_sources(sources):
    """
    Format source objects into a numbered Slack markdown list.
    Each line includes a linked title when a URI is available.
    """
    lines = []
    for idx, source in enumerate(sources, start=1):
        title = source.get("title") or "Source"
        uri = source.get("uri")
        if uri and title:
            lines.append(f"{idx}. <{uri}|{title}>")
        elif uri:
            lines.append(f"{idx}. {uri}")
        elif title:
            lines.append(f"{idx}. {title}")
    return "\n".join(lines)


def _fix_slack_markdown(text):
    """
    Convert common markdown patterns to Slack-friendly formatting.
    Normalizes bold, headers, and bullet markers.
    """
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    text = re.sub(r"^#+\s*(.*)$", r"*\1*", text, flags=re.MULTILINE)

    text = re.sub(r"^(\s{4,})\*\s+", r"\1• ", text, flags=re.MULTILINE)

    text = re.sub(r"^\*\s+", r"• ", text, flags=re.MULTILINE)
    return text


def _split_text(text, limit=2900):
    """
    Split long text into chunks under the Slack block size limit.
    Prefers breaking at whitespace where possible.
    """
    chunks = []
    while len(text) > limit:
        split_index = text.rfind(" ", 0, limit)
        if split_index == -1:
            split_index = limit
        chunks.append(text[:split_index])
        text = text[split_index:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def _normalize_cmd(text: str) -> str:
    """
    Normalize user input for exact command matching.
    Trims, lowercases, and collapses repeated whitespace.
    """
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _easter_egg_response(question_raw: str):
    """
    Return canned responses for greetings and predefined prompts.
    Returns None when no easter egg response is matched.
    """
    q = _normalize_cmd(question_raw)

    greeting_triggers = {"hi", "hello", "hey"}

    greeting_responses = [
        "hello :P",
        "heyyy",
        "hi there",
        "what's up",
        "howdy",
        "yo",
        "hey hey",
        "bello",
    ]

    if q in greeting_triggers:
        return random.choice(greeting_responses)

    if q == "tell me a joke":
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything.",
            "I told my friend 10 jokes to make him laugh. Sadly, no pun in ten did.",
            "Why did the scarecrow win an award? Because he was outstanding in his field.",
            "I'm reading a book about anti-gravity. It's impossible to put down.",
            "Why don't skeletons fight each other? They don't have the guts.",
            "What do you call fake spaghetti? An impasta.",
            "Why did the math book look sad? Because it had too many problems.",
            "I used to play piano by ear, but now I use my hands.",
            "Why did the golfer bring two pairs of pants? In case he got a hole in one.",
            "What do you call cheese that isn't yours? Nacho cheese.",
            "Why did the coffee file a police report? It got mugged.",
            "Why don't eggs tell jokes? They'd crack each other up.",
            "What did one wall say to the other wall? I'll meet you at the corner.",
            "Why can't your nose be 12 inches long? Because then it would be a foot.",
            "Why did the bicycle fall over? Because it was two tired.",
            "What did the ocean say to the beach? Nothing, it just waved.",
            "Why did the student eat his homework? Because the teacher said it was a piece of cake.",
            "What kind of tree fits in your hand? A palm tree.",
            "Why don't oysters donate to charity? Because they're shellfish.",
            "I asked the librarian if the library had books about paranoia. She whispered, 'They're right behind you.'",
        ]
        return random.choice(jokes)

    exact = {
        "good bot": "thank u :)",
        "bad bot": "sorry :(",
        "ill": "INI",
        "who are you": "I am batman",
        "what is the meaning of life": "42",
        "what is love": "baby don't hurt me",
    }

    return exact.get(q)


def _ask_and_respond(question, access_token, user_id, respond):
    """
    Query Discovery Engine and send a formatted Slack response.
    Includes fallback search sources and user-facing error handling.
    """
    try:
        response = answer_query(
            query=question,
            access_token=access_token,
            user_pseudo_id=user_id,
        )
        answer_text, sources, skipped_reasons = extract_answer_and_citations(response)

        if skipped_reasons:
            try:
                search_response = search_query(
                    query=question,
                    access_token=access_token,
                    user_pseudo_id=user_id,
                )
                search_sources = extract_search_results(search_response)
                if search_sources:
                    sources = search_sources
            except Exception as e:
                print(f"[ask] search fallback error: {e}")

        if not answer_text:
            if skipped_reasons:
                respond(
                    text="I can’t find an answer to that. You might not have access to documents with that information",
                    response_type="ephemeral",
                )
                return
            respond(
                text="I can’t find an answer to that. You might not have access to documents with that information",
                response_type="ephemeral",
            )
            return

        formatted_answer = _fix_slack_markdown(answer_text)
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Q:* {question}"}}
        ]

        for chunk in _split_text(formatted_answer):
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": chunk}}
            )

        if sources:
            sources_text = _format_sources(sources)
            if sources_text:
                blocks.append({"type": "divider"})
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Sources:*\n{sources_text}",
                        },
                    }
                )

        respond(blocks=blocks, response_type="in_channel")
    except Exception as e:
        print(f"[ask] error: {e}")
        respond(
            text="Sorry, there was an error answering your question.",
            response_type="ephemeral",
        )


@app.command("/ask")
def ask_command(ack, body, respond):
    """
    Handle the /ask Slack command end to end.
    Validates input, auth, limits, and dispatches async answering.
    """
    ack()
    question = (body.get("text") or "").strip()
    if not question:
        respond(text="Usage: /ask <question>", response_type="ephemeral")
        return

    egg = _easter_egg_response(question)
    if egg:
        respond(text=egg, response_type="in_channel")
        return

    user_id = body.get("user_id")
    if not user_id:
        respond(text="Missing Slack user id.", response_type="ephemeral")
        return

    profile = _slack_user_profile(user_id)
    email = profile.get("email") if profile else None
    if not email:
        respond(
            text="Unable to resolve your Slack email. Ask a developer to check app scopes.",
            response_type="ephemeral",
        )
        return

    user = get_user_entity(email)
    if user is None:
        name = profile.get("real_name") or profile.get("display_name") or email
        add_user(sub=None, name=name, email=email, picture=None, groups=[])

    is_allowed = check_and_log_query(email, limit=10, hours=24)

    if not is_allowed:
        respond(
            text="You've reached your limit of 10 queries per 24 hours.",
            response_type="ephemeral",
        )
        return

    access_token = get_valid_access_token(email)
    if not access_token:
        base = PUBLIC_BASE_URL.rstrip("/") if PUBLIC_BASE_URL else ""
        auth_link = f"{base}/login" if base else "/login"
        respond(
            text=(
                "To use /ask, please connect your Illini Media Google account):\n"
                f"{auth_link}"
            ),
            response_type="ephemeral",
        )
        return

    respond(text="Thinking...", response_type="ephemeral")
    Thread(
        target=_ask_and_respond,
        args=(question, access_token, user_id, respond),
        daemon=True,
    ).start()
