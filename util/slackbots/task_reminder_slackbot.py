from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from util.task_reminder import notify_shift_start, reset_weekly_tasks

TIMEZONE = ZoneInfo("America/Chicago")

scheduler = BackgroundScheduler(timezone=TIMEZONE)

# Monday shifts
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TIMEZONE),
    args=["monday", "09:00"],
    id="mon_0900",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="mon", hour=14, minute=0, timezone=TIMEZONE),
    args=["monday", "14:00"],
    id="mon_1400",
)

# Tuesday shifts
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="tue", hour=9, minute=0, timezone=TIMEZONE),
    args=["tuesday", "09:00"],
    id="tue_0900",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="tue", hour=12, minute=0, timezone=TIMEZONE),
    args=["tuesday", "12:00"],
    id="tue_1200",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="tue", hour=15, minute=0, timezone=TIMEZONE),
    args=["tuesday", "15:00"],
    id="tue_1500",
)

# Wednesday shifts
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="wed", hour=9, minute=0, timezone=TIMEZONE),
    args=["wednesday", "09:00"],
    id="wed_0900",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="wed", hour=13, minute=0, timezone=TIMEZONE),
    args=["wednesday", "13:00"],
    id="wed_1300",
)

# Thursday shifts
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="thu", hour=9, minute=0, timezone=TIMEZONE),
    args=["thursday", "09:00"],
    id="thu_0900",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="thu", hour=12, minute=0, timezone=TIMEZONE),
    args=["thursday", "12:00"],
    id="thu_1200",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="thu", hour=13, minute=0, timezone=TIMEZONE),
    args=["thursday", "13:00"],
    id="thu_1300",
)

# Friday shifts
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="fri", hour=9, minute=0, timezone=TIMEZONE),
    args=["friday", "09:00"],
    id="fri_0900",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="fri", hour=11, minute=0, timezone=TIMEZONE),
    args=["friday", "11:00"],
    id="fri_1100",
)
scheduler.add_job(
    notify_shift_start,
    CronTrigger(day_of_week="fri", hour=14, minute=0, timezone=TIMEZONE),
    args=["friday", "14:00"],
    id="fri_1400",
)

# Sunday midnight — reset all tasks for the new week
scheduler.add_job(
    reset_weekly_tasks,
    CronTrigger(day_of_week="sun", hour=0, minute=0, timezone=TIMEZONE),
    id="weekly_reset",
)

scheduler.start()
