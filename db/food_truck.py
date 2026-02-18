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
    logger.info(f"Registering new truck with name {name}...")
    logger.debug(
        f"Name= {name}; Cuisine= {cuisine}; Emoji= {emoji}; URL= {url}; Email= {email};"
    )
    truck = foodTruck(
        registered_at=datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None),
        name=name,
        cuisine=cuisine,
        emoji=emoji,
        url=url,
        email=email,
    )
    truck.put()

    logger.info(f"Created truck with UID = {truck.uid}.")
    return truck.to_dict()


# Deregister a food truck from the system entirely
def deregister_food_truck(uid):
    logger.info(f"Deleting truck with UID = {uid}...")
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        truck.key.delete()
        logger.info("Truck deleted.")
        return True
    else:
        logger.info("Truck not found.")
        return False


# Modify a truck's registration
def modify_food_truck(uid, name, cuisine, emoji, url, email):
    logger.info(f"Modifying truck with UID = {uid}")
    logger.debug(
        f"Name= {name}; Cuisine= {cuisine}; Emoji= {emoji}; URL= {url}; Email= {email};"
    )
    truck = foodTruck.get_by_id(uid)

    if truck:
        truck.name = name
        truck.cuisine = cuisine
        truck.emoji = emoji
        truck.url = url
        truck.email = email

        truck.put()
        logger.info("Truck modified.")

    else:
        logger.info("Truck not found.")
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
    logger.debug(
        f"Lat= {lat}; Lon= {lon}; Nearest Address= {nearest_address}; Location Desc.= {location_desc}; Start Time= {start_time}; End Time= {end_time}; Reported By= {reported_by}; Recurrence ID= {recurrence_id}"
    )
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

    logger.info(f"Created loctime with UID = {loctime.uid}.")
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
    """
    Adds multiple loctimes separated by one week intervals until specified end date (repeating loctime).
    Note: loctime can repeat on end date

    Arguments:
        `truck_uid` (`float`): The unique ID of the food truck.
        `lat` (`float`): The latitude coordinate of the location.
        `lon` (`float`): The longitude coordinate of the location.
        `nearest_address` (`str`): The nearest address to the location.
        `location_desc` (`str`): Description of the location.
        `start_time` (`datetime`): The start time of the loctime.
        `end_time` (`datetime`): The end time of the loctime.
        `reported_by` (`str`): The person reporting the loctime.
        `end_date` (`date`): The end date for the recurring series (repeats weekly).

    Returns:
        `bool`: `True` if all recurring loctimes were created successfully, `False` if overlap detected.

    """
    # check if any objects will overlap
    start_check = start_time
    end_check = end_time
    while start_check.date() <= end_date:
        if check_existing_loctime(truck_uid, start_check, end_check):
            logger.warning(f"There is a loctime overlap at {start_check}")
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
        logger.info("Loctime deleted.")
        return True
    else:
        logger.info("Loctime not found.")
        return False


# Removes all locTimes with the passed recurrence_id
def remove_truck_loctime_repeat(recurrence_id):
    """
    Removes all repeating loctimes that were created together(same recurrence_id).

    Arguments:
        `recurrence_id` (`str`): The unique recurrence ID that groups repeating times together to delete.

    Returns:
        `int`: The number of loctimes that was deleted.
    """
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
    logger.debug(
        f"Lat= {lat}; Lon= {lon}; Nearest Address= {nearest_address}; Location Desc.= {location_desc}; Start Time= {start_time}; End Time= {end_time}; Reported By= {reported_by}"
    )
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
        logger.info("Loctime modified.")

    else:
        logger.info("Loctime not found.")
        return None


# Removes any locTimes where the end time has passed
def remove_old_loc_times():
    logger.debug("Removing expired loctimes...")
    cur_time = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
    logger.debug(f"Current time = {cur_time}")

    expired_loc_times = foodTruckLocTime.query(
        foodTruckLocTime.end_time < cur_time
    ).fetch()

    ndb.delete_multi([locTime.key for locTime in expired_loc_times])

    logger.debug(f"Deleted {len(expired_loc_times)} loctime(s).")
    return len(expired_loc_times)


# Returns true if there is a loctime that overlaps with start_time or end_time (Expects all times in UTC)
def check_existing_loctime(truck_uid, start_time, end_time):
    logger.debug("Checking for overlapping loctimes...")
    logger.debug(f"truck_uid  = {truck_uid}")
    logger.debug(f"start_time = {start_time}")
    logger.debug(f"end_time   = {end_time}")
    loctimes = get_all_loctimes_for_truck(int(truck_uid))
    logger.debug("Retrieved all loctimes.")

    for loctime in loctimes:
        logger.debug(f"Checking loctime with uid = {loctime['uid']}")
        exst_start = loctime["start_time"]
        exst_end = loctime["end_time"]

        if (
            exst_start < start_time < exst_end
            or exst_start < end_time < exst_end
            or (start_time < exst_start and exst_end < end_time)
        ):
            logger.debug("Found loctime with overlapping times.")
            return True

    logger.debug("Did not find any overlapping loctimes.")
    return False


# Returns true if there is a loctime that overlaps with start_time or end_time (Based on locTime's UID) (Expects all times in UTC)
def check_existing_loctime_notruck(uid, start_time, end_time):
    logger.info("Checking for overlapping loctimes...")
    logger.debug(f"uid        = {uid}")
    logger.debug(f"start_time = {start_time}")
    logger.debug(f"end_time   = {end_time}")
    loctimes = get_all_loctimes_for_truck(
        foodTruckLocTime.get_by_id(int(uid)).truck_uid
    )
    logger.debug("Retrieved all loctimes.")

    for loctime in loctimes:
        logger.debug(f"Checking loctime with uid = {loctime['uid']}")
        exst_start = loctime["start_time"]
        exst_end = loctime["end_time"]

        if exst_start < start_time < exst_end or exst_start < end_time < exst_end:
            logger.debug("Found loctime with overlapping times.")
            if int(loctime["uid"]) != int(uid):
                logger.debug("Confirmed that this is not the loctime being modified.")
                return True
            logger.debug("This is the loctime being modified. Skipping...")

    logger.debug("Did not find any overlapping loctimes.")
    return False


# Get the registration information for all trucks
def get_all_registered_trucks():
    logger.info("Getting all registered trucks...")
    trucks = sorted(
        [truck.to_dict() for truck in foodTruck.query().fetch()],
        key=lambda x: x.get("name", "").lower(),
    )
    logger.debug("Done.")
    return trucks


# Get the registration for a truck by its UID
def get_registration_by_id(uid):
    logger.info(f"Getting registration for truck with UID = {uid}...")
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        logger.debug("Done.")
        return truck.to_dict()
    else:
        logger.info("Not found.")
        return None


# Get every locTime for all trucks (and clear all expired times)
def get_all_truck_loctimes():
    remove_old_loc_times()
    locTimes = [locTime.to_dict() for locTime in foodTruckLocTime.query().fetch()]
    return locTimes


# Get every locTime associated with a specific truck's UID (Sorted by start_time) (and clear all expired times)
def get_all_loctimes_for_truck(truck_uid):
    logger.debug(f"Getting all loctimes for truck with UID = {truck_uid}...")
    remove_old_loc_times()
    locTimes = (
        foodTruckLocTime.query(foodTruckLocTime.truck_uid == float(truck_uid))
        .order(foodTruckLocTime.start_time)
        .fetch()
    )

    logger.debug("Done.")
    return [locTime.to_dict() for locTime in locTimes]


# Get a specific loctime from its UID
def get_loctime_by_id(uid):
    logger.debug(f"Getting loctime with UID = {uid}...")
    loctime = foodTruckLocTime.get_by_id(uid)

    if loctime is not None:
        logger.debug("Done.")
        return loctime.to_dict()
    else:
        logger.debug("Not found.")
        return None


# Get all trucks with every locTime for each truck
def get_all_trucks_with_loctimes():
    logger.debug("Getting all trucks and loctimes...")
    all_trucks = get_all_registered_trucks()
    result = []

    for truck in all_trucks:
        logger.debug(f"Loop: Truck with UID = {truck['uid']}")
        truck_uid = truck.get("uid")

        truck["cur_loctime"] = {}
        truck["nxt_loctime"] = {}

        # Get every locTime for the truck
        loctimes = get_all_loctimes_for_truck(truck_uid)

        if len(loctimes) >= 2:
            logger.debug("Truck has at least 2 loctimes.")
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
                logger.debug("Setting both current and next loctime...")
                truck["cur_loctime"] = loctime1
                truck["nxt_loctime"] = loctime2
                logger.debug("\Done.")
            else:
                logger.debug("Setting next loctime...")
                truck["nxt_loctime"] = loctime1
                logger.debug("Done.")

        elif len(loctimes) == 1:
            logger.debug("Truck has 1 loctime.")
            loctime1 = loctimes[0]
            exst_start = loctime1["start_time"]
            exst_end = loctime1["end_time"]

            if (
                exst_start
                < datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None)
                < exst_end
            ):
                logger.debug("Setting current loctime...")
                truck["cur_loctime"] = loctime1
                logger.debug("Done.")
            else:
                logger.debug("Setting next loctime...")
                truck["nxt_loctime"] = loctime1
                logger.debug("Done.")

        result.append(truck)
        logger.debug("Added to list.")

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
