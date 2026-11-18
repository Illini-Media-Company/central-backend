from flask import Blueprint, render_template
from constants import EQUIPMENT_ACCESS_GROUP
from util.security import restrict_to
from datetime import date, datetime
from db.equipment import list_equipment, get_equipment

equipment_routes = Blueprint("equipment_routes", __name__, url_prefix="/equipment")


@equipment_routes.route("/dashboard", methods=["GET"])
@restrict_to(EQUIPMENT_ACCESS_GROUP)
def dashboard():
    return render_template("equipment.html")


def getAllEquipment():
    return [one_equipment_json(item) for item in list_equipment()]


def one_equipment_json(item):
    data = item.to_dict()
    data.pop("history", None)
    for field, value in data.items():
        if isinstance(value, (date, datetime)):
            data[field] = value.isoformat()
    return data


@equipment_routes.route("/", methods=["GET"])
@restrict_to(EQUIPMENT_ACCESS_GROUP)
def listEquipment():
    equipment = getAllEquipment()
    return {"equipment": equipment}


@equipment_routes.route("/<barcode_id>", methods=["GET"])
@restrict_to(EQUIPMENT_ACCESS_GROUP)
def lookupEquipment(barcode_id):
    try:
        item = get_equipment(barcode_id)
    except ValueError as e:
        return {"error": str(e)}, 400
    if item is None:
        return {"error": "Equipment not found."}, 404
    return {"equipment": one_equipment_json(item)}, 200
