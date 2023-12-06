from flask import Flask, request, render_template
import praw

app = Flask(__name__)

# Reddit app credentials
client_id = 'tJADWyLTm9saDIIYbPq8ow'
client_secret = 'lD7Qdk8NB5hMflJe7R1lH0MQXpm4oQ'
user_agent = 'story submission by u/Frogznlogs12'
username = 'Frogznlogs12'
password = 'NTS@5itwas'

# Reddit API wrapper
reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
    username=username,
    password=password
)

# test subreddit
subreddit_name = 'r/test_com23'

# URL input
url = input("Enter the URL: ")

# Submit URL as link post to Reddit
reddit.subreddit(subreddit_name).submit(url, url=url)

print(f"Posted to r/{subreddit_name}: {url}")



#using flask, question is how
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve data from the form
        url = request.form['url']

        # Submit the URL as a link post to Reddit
        subreddit = reddit.subreddit('YOUR_SUBREDDIT')
        subreddit.submit(url, url=url)

        return 'URL submitted to Reddit successfully!'

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
