"""
Backend-only test: post sample stories to the social Slack channel.
Run from project root with: python scripts/test_socials_post.py
Uses skip_db_update=True so no Datastore access is needed (Slack only).
Requires SLACK_BOT_TOKEN and SOCIAL_MEDIA_POSTS_CHANNEL_ID in env.
"""

import sys
import os

# Add project root so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SAMPLE_STORIES = [
    {
        "story_url": "https://dailyillini.com/2026/02/10/campus-event-celebrates-community/",
        "story_title": "Campus event celebrates community",
        "writer_name": "Jane Smith",
        "photographer_name": "Alex Chen",
        "image_url": "https://picsum.photos/800/500?random=1",
    },
    {
        "story_url": "https://dailyillini.com/2026/02/09/illinois-athletics-weekend-recap/",
        "story_title": "Illinois athletics weekend recap",
        "writer_name": "Marcus Johnson",
        "photographer_name": "Sam Rivera",
        "image_url": "https://picsum.photos/800/500?random=2",
    },
    {
        "story_url": "https://dailyillini.com/2026/02/08/new-research-lab-opens-on-campus/",
        "story_title": "New research lab opens on campus",
        "writer_name": "Emily Davis",
        "photographer_name": "Jordan Lee",
        "image_url": "https://picsum.photos/800/500?random=3",
    },
]


def run_test_posts():
    from util.slackbots.socials_slackbot import post_story_to_social_channel

    for i, sample in enumerate(SAMPLE_STORIES, 1):
        print(f"\n--- Sample {i}: {sample['story_title'][:50]}...")
        result = post_story_to_social_channel(
            story_url=sample["story_url"],
            story_title=sample["story_title"],
            writer_name=sample.get("writer_name"),
            photographer_name=sample.get("photographer_name"),
            image_url=sample.get("image_url"),
            skip_db_update=True,
        )
        print(f"  result: {result}")
    print("\nDone.")


if __name__ == "__main__":
    run_test_posts()
