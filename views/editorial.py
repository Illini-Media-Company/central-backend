import requests
import re

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

editorial_routes = Blueprint("editorial_routes", __name__, url_prefix="/editorial")

@editorial_routes.route("")
@login_required
def editorial():
    return render_template("editorial.html")

def fetch_info(post_id):
    api_url = f"https://dailyillini.com/wp-json/wp/v2/posts/{post_id}"
    response = requests.get(api_url)
    return response.json()

@editorial_routes.route("/get-published-url", methods=["GET"])
@login_required
def get_published_url(url):
    # url = request.form.get("url")

    post_id_match = re.search(r'post=(\d+)', url)
    if not post_id_match:
        return jsonify({"error": "Invalid URL format. Please enter a valid URL."}), 400

    post_id = post_id_match.group(1)

    data = fetch_info(post_id)

    if "code" in data and data["code"] == "rest_post_invalid_id":
        return jsonify({"result": "No publication could be found"})

    if "link" in data:
        return jsonify({"result": data["link"]})
    else:
        return jsonify({"result": "Unexpected response from the server"}), 500