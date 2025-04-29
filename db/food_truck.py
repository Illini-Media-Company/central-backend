from google.cloud import ndb
from datetime import datetime, timedelta

from . import client


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


# Register a new food truck with the database. Must be done before add
def register_food_truck(name, cuisine, emoji, url, email):
    truck = foodTruck(
        registered_at=datetime.now(),
        name=name,
        cuisine=cuisine,
        emoji=emoji,
        url=url,
        email=email,
    )
    truck.put()

    return truck.to_dict()


# Deregister a food truck from the system entirely
def deregister_food_truck(uid):
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        truck.key.delete()
        return True
    else:
        return False


# Modify a truck's registration
def modify_food_truck(uid, name, cuisine, emoji, url, email):
    print(f"MODIFYING TRUCK UID {uid}")
    truck = foodTruck.get_by_id(uid)

    if truck:
        print("Before:", truck.name, truck.cuisine, truck.emoji, truck.url, truck.email)
        truck.name = name
        truck.cuisine = cuisine
        truck.emoji = emoji
        truck.url = url
        truck.email = email
        print("After:", truck.name, truck.cuisine, truck.emoji, truck.url, truck.email)

        truck.put()

    else:
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
):
    truck = foodTruckLocTime(
        truck_uid=truck_uid,
        updated_at=datetime.now(),
        lat=lat,
        lon=lon,
        nearest_address=nearest_address,
        location_desc=location_desc,
        start_time=start_time,
        end_time=end_time,
        reported_by=reported_by,
    )
    truck.put()

    return truck.to_dict()


# Remove a locTime by the locTime's UID (and clear all expired times)
def remove_truck_loctime(uid):
    locTime = foodTruckLocTime.get_by_id(uid)

    remove_old_loc_times()

    if locTime is not None:
        locTime.key.delete()
        return True
    else:
        return False


# Modify a locTime by the locTime's UID
def modify_truck_loctime(
    uid, lat, lon, nearest_address, location_desc, start_time, end_time, reported_by
):
    print(f"MODIFYING LOCTIME UID {uid}")
    locTime = foodTruckLocTime.get_by_id(int(uid))

    if locTime:
        locTime.updated_at = (datetime.now(),)
        locTime.lat = lat
        locTime.lon = lon
        locTime.nearest_address = nearest_address
        locTime.location_desc = location_desc
        locTime.start_time = start_time
        locTime.end_time = end_time
        locTime.reported_by = reported_by

        locTime.put()

    else:
        return None


# Removes any locTimes where the end time has passed
def remove_old_loc_times():
    cur_time = datetime.now()

    expired_loc_times = foodTruckLocTime.query(
        foodTruckLocTime.end_time < cur_time
    ).fetch()

    ndb.delete_multi([locTime.key for locTime in expired_loc_times])

    return len(expired_loc_times)


# Get the registration information for all trucks
def get_all_registered_trucks():
    trucks = [truck.to_dict() for truck in foodTruck.query().fetch()]
    return trucks


# Get the registration for a truck by its UID
def get_registration_by_id(uid):
    truck = foodTruck.get_by_id(uid)

    if truck is not None:
        return truck.to_dict()
    else:
        return None


# Get every locTime for all trucks (and clear all expired times)
def get_all_truck_loctimes():
    remove_old_loc_times()
    locTimes = [locTime.to_dict() for locTime in foodTruckLocTime.query().fetch()]
    return locTimes


# Get every locTime associated with a specific truck's UID (Sorted by start_time) (and clear all expired times)
def get_all_loctimes_for_truck(truck_uid):
    remove_old_loc_times()
    locTimes = (
        foodTruckLocTime.query(foodTruckLocTime.truck_uid == float(truck_uid))
        .order(foodTruckLocTime.start_time)
        .fetch()
    )

    return [locTime.to_dict() for locTime in locTimes]


# Get a specific loctime from its UID
def get_loctime_by_id(uid):
    loctime = foodTruckLocTime.get_by_id(uid)

    if loctime is not None:
        return loctime.to_dict()
    else:
        return None


# Get all trucks with every locTime for each truck
def get_all_trucks_with_loctimes():
    all_trucks = get_all_registered_trucks()
    result = []

    for truck in all_trucks:
        truck_uid = truck.get("uid")

        # Get every locTime for the truck
        loc_times = get_all_loctimes_for_truck(truck_uid)

        # Add the locTimes to the truck
        truck["loc_times"] = loc_times

        result.append(truck)

    return result
