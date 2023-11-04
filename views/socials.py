from flask import (
    Blueprint,
    render_template,
    request
)
from flask_login import login_required
from db.story import get_all_stories, add_story, delete_all_stories


socials_routes = Blueprint('socials_routes', __name__, url_prefix='/socials')


@socials_routes.route('/dashboard')
@login_required
def dashboard():
    stories = get_all_stories()
    return render_template('socials.html', stories=stories)

@socials_routes.route('', methods=['GET'])
@login_required
def list_stories():
    return get_all_stories()

@socials_routes.route('', methods=['POST'])
@login_required
def create_story():
    title = request.form['title']
    url = request.form['url']
    posted_to = request.form['posted_to']
    add_story(title=title, url=url, posted_to=posted_to)
    return 'Story created.', 200

@socials_routes.route('/delete_all_story', methods=['POST'])
@login_required
def delete_all_story():
    delete_all_stories()
    return 'All stories deleted.'