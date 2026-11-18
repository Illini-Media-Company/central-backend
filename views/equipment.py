from flask import Blueprint, render_template
from constants import EQUIPMENT_ACCESS_GROUP
from util.security import restrict_to

equipment_routes = Blueprint("equipment_routes", __name__, url_prefix="/equipment")

@equipment_routes.route("/dashboard", methods=["GET"])
@restrict_to(EQUIPMENT_ACCESS_GROUP)
def dashboard():
    return render_template("equipment.html")

def getAllEquipment():
    # call Gus's database function
    return []

@equipment_routes.route("/", methods =["GET"])
@restrict_to(EQUIPMENT_ACCESS_GROUP)
def listEquipment():
    equipment = getAllEquipment()
    return {"equipment": equipment}