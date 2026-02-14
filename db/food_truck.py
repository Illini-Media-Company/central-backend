import uuid
from google.cloud import ndb
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

from . import client

logger = logging.getLogger(__name__)


# Registration information for a specific truck
class foodTruck(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    registered_at = ndb.DateTimeProperty()
    name = ndb.StringProperty()
    cuisine = ndb.StringProperty()
    emoji = ndb.StringProperty()
    url = ndb.StringProperty()
    email = ndb.StringProperty()


# Holds the time and location data with reference to a specific truck
class foodTruckLocTime(ndb.Model):
    uid = ndb.ComputedProperty(
        lambda self: self.key.id() if self.key else None, indexed=False
    )
    truck_uid = ndb.FloatProperty()  # The UID for the truck this is associated with
    updated_at = ndb.DateTimeProperty()
    lat = ndb.FloatProperty()
    lon = ndb.FloatProperty()
    nearest_address = ndb.StringProperty()
    location_desc = ndb.StringProperty()
    start_time = ndb.DateTimeProperty()
    end_time = ndb.DateTimeProperty()
    reported_by = ndb.StringProperty()
    recurrence_id = ndb.StringProperty()


# Register a new food truck with the database. Must be done before add
def register_food_truck(name, cuisine, emoji, url, email):
    logger.info("Registering new truck...")
    logger.debug(f"\tName    = {name}")
    logger.debug(f"\tCuisine = {cuisine}")
    logger.debug(f"\tEmoji   = {emoji}")
    logger.debug(f"\tURL     = {url}")
    logger.debug(f"\tEmail   = {email}")
    truck = foodTruck(
        registered_at=datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None),
        name=name,
        cuisine=cuisine,
        emoji=emoji,
        url=url,
        email=email,
    )
    truck.put()

    logger.debug(f"Created truck with UID = {truck.uid}.")
    return truck.to_dict()


# Deregister a food truck from the system entirely
def deregister_food_truck(uid):
    logger.info(f"Deregistering truck with UID = {uid}...")
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        truck.key.delete()
        logger.debug("\tTruck deleted.")
        return True
    else:
        logger.warning("\tTruck not found.")
        return False


# Modify a truck's registration
def modify_food_truck(uid, name, cuisine, emoji, url, email):
    logger.info(f"Modifying truck with UID = {uid}")
    logger.debug(f"\tNew name    = {name}")
    logger.debug(f"\tNew cuisine = {cuisine}")
    logger.debug(f"\tNew emoji   = {emoji}")
    logger.debug(f"\tNew URL     = {url}")
    logger.debug(f"\tNew email   = {email}")
    truck = foodTruck.get_by_id(uid)

    if truck:
        logger.debug(
            "\t\tBefore:",
            truck.name,
            truck.cuisine,
            truck.emoji,
            truck.url,
            truck.email,
        )
        truck.name = name
        truck.cuisine = cuisine
        truck.emoji = emoji
        truck.url = url
        truck.email = email

        truck.put()
        logger.debug("\tTruck modified.")

    else:
        logger.warning("\tTruck not found.")
        return None


# Add a locTime for a specific truck
def add_truck_loctime(
    truck_uid,
    lat,
    lon,
    nearest_address,
    location_desc,
    start_time,
    end_time,
    reported_by,
    recurrence_id=None,
):
    cur_time = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)

    logger.info(f"Creating new loctime for truck with UID = {truck_uid}...")
    logger.debug(f"\tLat             = {lat}")
    logger.debug(f"\tLon             = {lon}")
    logger.debug(f"\tNearest Address = {nearest_address}")
    logger.debug(f"\tLocation Desc.  = {location_desc}")
    logger.debug(f"\tStart Time      = {start_time}")
    logger.debug(f"\tEnd Time        = {end_time}")
    logger.debug(f"\tReported By     = {reported_by}")
    logger.debug(f"\tUpdated at      = {cur_time}")
    loctime = foodTruckLocTime(
        truck_uid=truck_uid,
        updated_at=cur_time,
        lat=lat,
        lon=lon,
        nearest_address=nearest_address,
        location_desc=location_desc,
        start_time=start_time,
        end_time=end_time,
        reported_by=reported_by,
        recurrence_id=recurrence_id,
    )
    loctime.put()

    logger.debug("Done.")
    return loctime.to_dict()


# add loctime objects that repeat til end_date
def add_truck_loctime_repeat(
    truck_uid,
    lat,
    lon,
    nearest_address,
    location_desc,
    start_time,
    end_time,
    reported_by,
    end_date,
):
    # check if any objects will overlap
    start_check = start_time
    end_check = end_time
    while start_check.date() <= end_date:
        if check_existing_loctime(truck_uid, start_check, end_check):
            logger.warning(f"\tThere is a loctime overlap at {start_check}")
            return False

        start_check += timedelta(weeks=1)
        end_check += timedelta(weeks=1)

    # add times
    recurrence_id = uuid.uuid4().hex
    while start_time.date() <= end_date:
        add_truck_loctime(
            truck_uid,
            lat,
            lon,
            nearest_address,
            location_desc,
            start_time,
            end_time,
            reported_by,
            recurrence_id,
        )

        start_time += timedelta(weeks=1)
        end_time += timedelta(weeks=1)
    return True


# Remove a locTime by the locTime's UID (and clear all expired times)
def remove_truck_loctime(uid):
    logger.info(f"Removing loctime with UID = {uid}...")
    locTime = foodTruckLocTime.get_by_id(uid)

    remove_old_loc_times()

    if locTime is not None:
        locTime.key.delete()
        logger.debug("\tLoctime deleted.")
        return True
    else:
        logger.warning("\tLoctime not found.")
        return False


# Removes all locTimes with the passed recurrence_id
def remove_truck_loctime_repeat(recurrence_id):
    keys = foodTruckLocTime.query(
        foodTruckLocTime.recurrence_id == recurrence_id
    ).fetch(keys_only=True)

    ndb.delete_multi(keys)

    return len(keys)


# Modify a locTime by the locTime's UID
def modify_truck_loctime(
    uid, lat, lon, nearest_address, location_desc, start_time, end_time, reported_by
):
    cur_time = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)

    logger.info(f"Modifying loctime with UID = {uid}...")
    logger.debug(f"\tLat             = {lat}")
    logger.debug(f"\tLon             = {lon}")
    logger.debug(f"\tNearest Address = {nearest_address}")
    logger.debug(f"\tLocation Desc.  = {location_desc}")
    logger.debug(f"\tStart Time      = {start_time}")
    logger.debug(f"\tEnd Time        = {end_time}")
    logger.debug(f"\tReported By     = {reported_by}")
    logger.debug(f"\tUpdated at      = {cur_time}")
    locTime = foodTruckLocTime.get_by_id(int(uid))

    if locTime:
        locTime.updated_at = cur_time
        locTime.lat = lat
        locTime.lon = lon
        locTime.nearest_address = nearest_address
        locTime.location_desc = location_desc
        locTime.start_time = start_time
        locTime.end_time = end_time
        locTime.reported_by = reported_by

        locTime.put()
        logger.debug("\tLoctime modified.")

    else:
        logger.warning("\tLoctime not found.")
        return None


# Removes any locTimes where the end time has passed
def remove_old_loc_times():
    logger.info("Removing expired loctimes...")
    cur_time = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
    logger.debug(f"\tCurrent time = {cur_time}")

    expired_loc_times = foodTruckLocTime.query(
        foodTruckLocTime.end_time < cur_time
    ).fetch()

    ndb.delete_multi([locTime.key for locTime in expired_loc_times])

    logger.debug(f"\tDeleted {len(expired_loc_times)} loctime(s).")
    return len(expired_loc_times)


# Returns true if there is a loctime that overlaps with start_time or end_time (Expects all times in UTC)
def check_existing_loctime(truck_uid, start_time, end_time):
    logger.info("Checking for overlapping loctimes...")
    logger.debug(f"\ttruck_uid  = {truck_uid}")
    logger.debug(f"\tstart_time = {start_time}")
    logger.debug(f"\tend_time   = {end_time}")
    loctimes = get_all_loctimes_for_truck(int(truck_uid))
    logger.debug("\tRetrieved all loctimes.")

    for loctime in loctimes:
        logger.debug(f"\tChecking loctime with uid = {loctime['uid']}")
        exst_start = loctime["start_time"]
        exst_end = loctime["end_time"]

        if (
            exst_start < start_time < exst_end
            or exst_start < end_time < exst_end
            or (start_time < exst_start and exst_end < end_time)
        ):
            logger.debug("\t\tFound loctime with overlapping times.")
            return True

    logger.warning("\tDid not find any overlapping loctimes.")
    return False


# Returns true if there is a loctime that overlaps with start_time or end_time (Based on locTime's UID) (Expects all times in UTC)
def check_existing_loctime_notruck(uid, start_time, end_time):
    logger.info("Checking for overlapping loctimes...")
    logger.debug(f"\tuid        = {uid}")
    logger.debug(f"\tstart_time = {start_time}")
    logger.debug(f"\tend_time   = {end_time}")
    loctimes = get_all_loctimes_for_truck(
        foodTruckLocTime.get_by_id(int(uid)).truck_uid
    )
    logger.debug("\tRetrieved all loctimes.")

    for loctime in loctimes:
        logger.debug(f"\tChecking loctime with uid = {loctime['uid']}")
        exst_start = loctime["start_time"]
        exst_end = loctime["end_time"]

        if exst_start < start_time < exst_end or exst_start < end_time < exst_end:
            logger.debug("\t\tFound loctime with overlapping times.")
            if int(loctime["uid"]) != int(uid):
                logger.debug(
                    "\t\tConfirmed that this is not the loctime being modified."
                )
                return True
            logger.debug("\t\tThis is the loctime being modified. Skipping...")

    logger.warning("\tDid not find any overlapping loctimes.")
    return False


# Get the registration information for all trucks
def get_all_registered_trucks():
    logger.info("Getting all registered trucks...")
    trucks = sorted(
        [truck.to_dict() for truck in foodTruck.query().fetch()],
        key=lambda x: x.get("name", "").lower(),
    )
    logger.debug("\tDone.")
    return trucks


# Get the registration for a truck by its UID
def get_registration_by_id(uid):
    logger.info(f"Getting registration for truck with UID = {uid}...")
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        logger.debug("\tDone.")
        return truck.to_dict()
    else:
        logger.warning("\tNot found.")
        return None


# Get every locTime for all trucks (and clear all expired times)
def get_all_truck_loctimes():
    logger.info("Getting all loctimes for all trucks...")
    remove_old_loc_times()
    locTimes = [locTime.to_dict() for locTime in foodTruckLocTime.query().fetch()]
    logger.debug("\tDone.")
    return locTimes


# Get every locTime associated with a specific truck's UID (Sorted by start_time) (and clear all expired times)
def get_all_loctimes_for_truck(truck_uid):
    logger.info(f"\tGetting all loctimes for truck with UID = {truck_uid}...")
    remove_old_loc_times()
    locTimes = (
        foodTruckLocTime.query(foodTruckLocTime.truck_uid == float(truck_uid))
        .order(foodTruckLocTime.start_time)
        .fetch()
    )

    logger.debug("\tDone.")
    return [locTime.to_dict() for locTime in locTimes]


# Get a specific loctime from its UID
def get_loctime_by_id(uid):
    logger.info(f"Getting loctime with UID = {uid}...")
    loctime = foodTruckLocTime.get_by_id(uid)

    if loctime is not None:
        logger.debug("\tDone.")
        return loctime.to_dict()
    else:
        logger.debug("\tFound.")
        return None


# Get all trucks with every locTime for each truck
def get_all_trucks_with_loctimes():
    logger.info("Getting all trucks and loctimes...")
    all_trucks = get_all_registered_trucks()
    result = []

    for truck in all_trucks:
        logger.debug(f"\tLoop: Truck with UID = {truck['uid']}")
        truck_uid = truck.get("uid")

        truck["cur_loctime"] = {}
        truck["nxt_loctime"] = {}

        # Get every locTime for the truck
        loctimes = get_all_loctimes_for_truck(truck_uid)

        if len(loctimes) >= 2:
            logger.debug("\t\tTruck has at least 2 loctimes.")
            # Since these are sorted alphabetically, we can just get the first two
            loctime1 = loctimes[0]
            loctime2 = loctimes[1]

            exst_start = loctime1["start_time"]
            exst_end = loctime1["end_time"]

            # Check if this is the current loctime
            if (
                exst_start
                < datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
                < exst_end
            ):
                logger.debug("\t\tSetting both current and next loctime...")
                truck["cur_loctime"] = loctime1
                truck["nxt_loctime"] = loctime2
                logger.debug("\t\t\tDone.")
            else:
                logger.debug("\t\tSetting next loctime...")
                truck["nxt_loctime"] = loctime1
                logger.debug("\t\t\tDone.")

        elif len(loctimes) == 1:
            logger.debug("\t\tTruck has 1 loctime.")
            loctime1 = loctimes[0]
            exst_start = loctime1["start_time"]
            exst_end = loctime1["end_time"]

            if (
                exst_start
                < datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
                < exst_end
            ):
                logger.debug("\t\tSetting current loctime...")
                truck["cur_loctime"] = loctime1
                logger.debug("\t\t\tDone.")
            else:
                logger.debug("\t\tSetting next loctime...")
                truck["nxt_loctime"] = loctime1
                logger.debug("\t\t\tDone.")

        result.append(truck)
        logger.debug("\tAdded to list.")

    logger.debug("Done.")
    return result


# Get all cuisine types from registered trucks
def get_all_cuisines():
    cuisines = set()
    trucks = foodTruck.query().fetch()

    for truck in trucks:
        if truck.cuisine:
            cuisines.add(truck.cuisine)

    return sorted(list(cuisines))
