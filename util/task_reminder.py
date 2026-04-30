import logging

from db.task_reminder import (
    get_all_tasks,
    mark_task_done,
    reset_all_tasks,
    get_tasks_for_shift,
)
from util.slackbots.general import dm_user_by_email

logger = logging.getLogger(__name__)


def get_tasks():
    return get_all_tasks()


def mark_done(task_id):
    task = mark_task_done(task_id)
    if task is None:
        return None, ("Task not found", 404)
    logger.info(f"Task {task_id} marked done by {task['username']}")
    return task, None


def reset_weekly_tasks():
    tasks = reset_all_tasks()
    logger.info("All tasks reset for new week")
    return tasks


def send_slack_notification(task):
    email = task.get("email")
    if not email:
        logger.warning(f"No email set for {task['username']}, skipping notification")
        return None, (f"No email set for {task['username']}", 400)

    if task.get("is_done"):
        logger.info(f"Task for {task['username']} already done this week, skipping")
        return None, (f"Task already completed this week for {task['username']}", 200)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Task Reminder: {task['task_description']}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Hi {task['username']}! Here is your task reminder for this shift:\n\n"
                    f"*Task:* {task['task_description']}\n"
                    f"*How often:* {task['task_frequency']}"
                ),
            },
        },
    ]

    result = dm_user_by_email(
        email=email,
        text=f"Task Reminder: {task['task_description']}",
        blocks=blocks,
    )

    if result.get("ok"):
        logger.info(f"Slack notification sent to {task['username']} ({email})")
        return result, None
    else:
        logger.error(f"Failed to notify {task['username']}: {result.get('error')}")
        return None, (result.get("error"), 500)


def notify_shift_start(day, start_time):
    """Called by the scheduler at each shift start time."""
    tasks = get_tasks_for_shift(day, start_time)
    if not tasks:
        logger.info(f"No tasks for {day} at {start_time}")
        return

    for task in tasks:
        _, err = send_slack_notification(task)
        if err:
            logger.warning(f"Notification skipped for {task['username']}: {err}")
