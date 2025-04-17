from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from db.map_point import add_point, remove_point
from datetime import datetime

scheduler = BackgroundScheduler()
scheduler.start()


def add(title, lat, long, url, start_date, end_date, image, address):
    point = add_point(
        title=title,
        lat=lat,
        long=long,
        url=url,
        start_date=start_date,
        end_date=end_date,
        image=image,
        address=address,
    )
    trigger = DateTrigger(end_date, timezone="America/Chicago")
    scheduler.add_job(trigger=trigger, func=remove, args=[int(point["uid"])])

    print(f"Point will be deleted {end_date}")


def remove(uid):
    remove_point(uid)
