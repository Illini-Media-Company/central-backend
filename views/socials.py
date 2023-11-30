from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from flask_login import login_required
import praw


socials_routes = Blueprint('socials_routes', __name__, url_prefix='/socials')

def post_to_reddit(title, url, subreddit, client_id, client_secret, user_agent, reddit_username, reddit_password):
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        username=reddit_username,
        password=reddit_password
    )
    try:
        subreddit = reddit.subreddit(subreddit)  # Fix: Use the provided subreddit parameter
        submission = subreddit.submit(title, url=url)
        return submission.url
    except Exception as e:
        return str(e)

@socials_routes.route('/dashboard')
@login_required
def dashboard():
    return render_template('socials.html')

@socials_routes.route('/submit-story', methods=['POST'])
def submit_story():
    print('text')
    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        subreddit = 'test_com23'

        # Reddit API credentials
        client_id = 'cWPduh2pXLRa_4Ku8lxY6A'
        client_secret = '7F9Xw6cbZ3pqxaoZFNdZ4eCuvxZCKg'
        user_agent = 'story submission by u/Frogznlogs12'
        reddit_username = 'Frogznlogs12'
        reddit_password = 'NTS@5itwas'

        submission_url = post_to_reddit(title, url, subreddit, client_id, client_secret, user_agent, reddit_username, reddit_password)
        print('anything')
        print(submission_url)
        if submission_url:
            return redirect(url_for('socials_routes.dashboard', url=submission_url))
        else:
            return "Error posting to Reddit."

    return render_template('socials.html')