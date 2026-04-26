import datetime
import logging 
from util.slackbots._slackbot import app
from constants import SLACK_BOT_TOKEN
from util.slackbots.general import dm_user_by_email, dm_channel_by_id

logger = logging.getLogger(__name__)

TEMP_ID = "C12345678"  # Placeholder channel ID for notifications

def send_writer_assignment_notification(email: str, story_title: str) -> dict:
    """Notifies a writer they have been assigned a new story via DM."""
    
    message_text = (
        f"📰 *New Assignment!*\n"
        f"You've been assigned to write: *{story_title}*.\n"
        f"Please check the Content Doc to update your status and add any graphic requests."
    )
    
    # dm_user_by_email automatically handles the email-to-ID lookup and error logging
    return dm_user_by_email(email=email, text=message_text)
    

def send_copy_chief_notification(story_title: str, snow_link: str) ->dict:
    """Pings the copy chief channel when a story hits 2nd edited."""
    
    message_text = (
        f"✅ *Story Ready for Slotting*\n"
        f"*{story_title}* has passed 2nd edit!\n"
        f"Snow Link: {snow_link}"
    )
    
    # dm_channel_by_id sends directly to the specified channel
    return dm_channel_by_id(channel_id=TEMP_ID, text=message_text)
    
    
def send_visual_reminder_notification(email: str, story_title: str, visual_type: str, due_date: datetime.date) -> dict:
    """Reminds photo/graphics editors via DM for missing assets."""
    
    formatted_date = due_date.strftime("%B %d, %Y")
    
    message_text = (
        f"⚠️ *Missing Asset Reminder*\n"
        f"The {visual_type} for *{story_title}* is still missing (Due: {formatted_date}).\n"
        f"Please update the Content Doc as soon as possible!"
    )
    
    return dm_user_by_email(email=email, text=message_text)