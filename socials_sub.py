

from flask import Flask, render_template, request, redirect, url_for
import pra
f

app = Flask("submit_reddit")

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

@app.route('/', methods=['GET', 'POST'])
def submit_story():
    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        subreddit = request.form['test_com23']

        # Reddit API credentials
        client_id = 'tJADWyLTm9saDIIYbPq8ow'
        client_secret = 'lD7Qdk8NB5hMflJe7R1lH0MQXpm4oQ'
        user_agent = 'story submission by u/Frogznlogs12'
        reddit_username = 'Frogznlogs12'
        reddit_password = 'NTS@5itwas'

        submission_url = post_to_reddit(title, url, subreddit, client_id, client_secret, user_agent, reddit_username, reddit_password)
        print(submission_url)
        if submission_url:
            return redirect(url_for('socials_routes.dashboard', url=submission_url))
        else:
            return "Error posting to Reddit."

    return render_template('socials.html')

@app.route('/success/<url>')
def success(url):
    return render_template('confirmation_socials_.html')  # Fix: Correct the template name

if __name__ == '__main__':
    app.run(debug=True)