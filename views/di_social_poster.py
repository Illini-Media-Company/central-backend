"""
Flask routes for DI social stories dashboard.

Displays a read-only dashboard showing social media posting status for stories.
Includes pagination and search functionality.

Last modified by Aryaa Rathi on Feb 19, 2026
"""

from datetime import datetime
from flask import Blueprint, render_template, request
from flask_login import login_required

from db.socials_poster import get_all_stories, post_sample_stories_to_slack

di_social_poster_routes = Blueprint(
    "di_social_poster_routes", __name__, url_prefix="/di-socials-poster"
)


@di_social_poster_routes.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    """
    Render the DI social stories dashboard with pagination.
    Shows 20 stories per page, ordered by story_posted_timestamp (most recent first).
    """
    # Handle pagination
    page = int(request.args.get("page", 1))
    PER_PAGE = 20

    # Get all stories ordered by most recent first
    all_stories = get_all_stories()

    # Sort by story_posted_timestamp descending (most recent first)
    # Handle None timestamps by putting them at the end
    all_stories.sort(
        key=lambda x: x.get("story_posted_timestamp") or datetime.min, reverse=True
    )

    total_stories = len(all_stories)

    # Calculate pagination slice
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    stories = all_stories[start:end]

    return render_template(
        "di_social_poster/dashboard.html",
        stories=stories,
        total_stories=total_stories,
        page=page,
        per_page=PER_PAGE,
    )


@di_social_poster_routes.route("/test-post", methods=["POST"])
@login_required
def test_post():
    """
    Post sample stories to the social Slack channel for testing.
    Adds stories to DB, posts to Slack, and stores message timestamps.
    """
    post_sample_stories_to_slack()
    return "Sample stories posted.", 200
