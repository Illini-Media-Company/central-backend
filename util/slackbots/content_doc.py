import datetime
import logging 

from util.slackbots.general import ( 
    dm_user_by_email,
    dm_channel_by_id
)

# Initialize logger for this module
logger = logging.getLogger(__name__)

COPY_CHIEF_CHANNEL_ID = "C1234567890" 

def send_writer_assignment_notification(email: str, story_title: str) -> dict:
    """Notifies a writer they have been assigned a new story via DM."""
    logger.info("[Slackbot] Triggering writer assignment notification for '%s' to %s.", story_title, email)
    
    message_text = (
        f"📰 *New Assignment!*\n"
        f"You've been assigned to write: *{story_title}*.\n"
        f"Please check the Content Doc to update your status and add any graphic requests."
    )
    
    return dm_user_by_email(email=email, text=message_text)


def send_copy_chief_notification(story_title: str, snow_link: str) -> dict:
    """Pings the copy chief channel when a story hits 2nd edited."""
    logger.info("[Slackbot] Triggering copy chief 'Ready for Slotting' notification for '%s'.", story_title)
    
    message_text = (
        f"✅ *Story Ready for Slotting*\n"
        f"*{story_title}* has passed 2nd edit!\n"
        f"Snow Link: {snow_link}"
    )
    
    return dm_channel_by_id(channel_id=COPY_CHIEF_CHANNEL_ID, text=message_text)


def send_visual_reminder_notification(email: str, story_title: str, visual_type: str, due_date: datetime.date) -> dict:
    """Reminds photo/graphics editors via DM for missing assets."""
    logger.info("[Slackbot] Triggering %s reminder for '%s' to %s.", visual_type, story_title, email)
    
    formatted_date = due_date.strftime("%B %d, %Y")
    
    message_text = (
        f"⚠️ *Missing Asset Reminder*\n"
        f"The {visual_type} for *{story_title}* is still missing (Due: {formatted_date}).\n"
        f"Please update the Content Doc as soon as possible!"
    )
    
    return dm_user_by_email(email=email, text=message_text)