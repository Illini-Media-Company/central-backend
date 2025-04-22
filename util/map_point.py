from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from db.map_point import add_point, remove_point

from datetime import datetime
from db.json_store import json_store_set, json_store_get, JSONStore

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
    job_id = f"map_point_{point['uid']}"
    job_data = {
        "uid": point["uid"],
        "end_date": end_date.isoformat(),
    }

    # Storing job data
    json_store_set(job_id, job_data)

    # Updating master job list
    job_list = json_store_get("map_point_jobs") or []
    if job_id not in job_list:
        job_list.append(job_id)
        json_store_set("map_point_jobs", job_list)

    # Scheduled locally
    trigger = DateTrigger(end_date, timezone="America/Chicago")
    scheduler.add_job(id=job_id, trigger=trigger, func=remove, args=[int(point["uid"])])

    print(f"Point will be deleted {end_date}")


def remove(uid):
    remove_point(uid)
    job_id = f"map_point_{uid}"

    # Removed from job list
    job_list = json_store_get("map_point_jobs") or []
    if job_id in job_list:
        job_list.remove(job_id)
        json_store_set("map_point_jobs", job_list)

    # Removed job data
    store_obj = JSONStore.get_by_id(job_id)
    if store_obj:
        store_obj.key.delete()

#Restoring previous jobs in case of app crash/restart
job_ids = json_store_get("map_point_jobs") or []
for job_id in job_ids:
    job_data = json_store_get(job_id)
    if not job_data:
        continue

    uid = job_data.get("uid")
    end_date_str = job_data.get("end_date")

    if not uid or not end_date_str:
        continue  # skip any malformed data, just in case

    if scheduler.get_job(job_id) is None:
        try:
            end_date = datetime.fromisoformat(end_date_str)
            trigger = DateTrigger(end_date, timezone="America/Chicago")
            scheduler.add_job(id=job_id, trigger=trigger, func=remove, args=[int(uid)])
            print(f"Restored job {job_id} for {end_date}")
        except Exception as e:
            print(f"Failed to restore job {job_id}: {e}")