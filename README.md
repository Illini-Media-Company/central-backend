# central-backend

[app.dailyillini.com](https://app.dailyillini.com)

## Local Setup

### Prerequisites

Make sure you have all of the following installed on your computer:

- Python 3.11 (Different may cause issues for Google Cloud)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- Git
- [Java 11+](https://www.oracle.com/java/technologies/downloads/#java17) (check if you have it already by running `java --version` in a terminal)

### Steps

1. Clone this repo on your computer using either GitHub Desktop or the `git` CLI tool.

2. Get the `.env` file from the Lead Developer and place it in the `central-backend` folder you just cloned.

3. In a terminal window, run `gcloud auth login` to open a login page on your browser. Log in to your **@illinimedia.com** account, then return to the terminal. Following the prompt, set the current project to `central-backend-399421`.

4. Run the provided script for your OS to set up your development environment.

macOS or Linux:
```
./scripts/setup.sh
```

Windows:
```
.\scripts\setup.bat
```

5. Open a new terminal, and start the Google Cloud Datastore emulator.

```
gcloud beta emulators datastore start
```

6. In your original terminal, run the provided script to start `central-backend` on your computer.

macOS or Linux:
```
./scripts/run.sh
```

Windows:
```
.\scripts\run.bat
```

7. Open your favorite browser and navigate to <https://localhost:5001>. Ignore the "your connection is not private" warning; that's not an issue because no data is sent over the internet (the server is running on your computer).

## Slack Apps

Creating, using and running Slack apps (Copy Bot, Breaking News Bot, News Scraper) in development locally. Reference [Slack Documentation]([url](https://docs.slack.dev/tools/bolt-python/building-an-app)) for specific questions about the development process.

### Prerequisites

- Have the Central Backend running locally on your machine
- Receive access to the Central Backend Testing workspace on Slack from your supervisor ([http://onboardingapptesting.slack.com](http://onboardingapptesting.slack.com))

### Implementation

- The file `/util/slackbot.py` defines and creates the main Slack app, called IMC Bot.
  - The same file also defines the IMC Welcome Bot, which is an extention of the IMC Bot app and is responsible for sending welcome messages to everyone added to the workspace and routing them to the correct channels.
  - Most importantly, this file creates the `app` variable which is used by all other files referencing a Slack app. Additionally, it contains the function to initialize the app which is called from `main.py`.
- Slackbots that do not have Central Backend APIs (like the Copy Editing Bot) are located under `/util/xxx`.
- Slackbots that *have* Central Backend APIs (like the Breaking News Bot) are located under `/views/xxx`.
- All Slackbot files must import the main app (`from util.slackbot import app`) as well as the Bot Token (`from constants import SLACK_BOT_TOKEN`)
- All apps can define the username that the message is sent from. For example:
    ```
    app.client.chat_postMessage(
      token=SLACK_BOT_TOKEN,
      username="Whatever you want",
      channel={the ID of the channel with no braces},
      blocks=[
        (message blocks go here)
      ]
    )
    ```
- Message body can be created using the [Slack Block Kit Builder](https://app.slack.com/block-kit-builder/)

### Running Slackbots

- When running the Central Backend locally, it pulls all secrets from the `.env` file. These are development secrets and are (usually) different than the production secrets located in GitHub Actions.
- Because of this, the Slack App will run the app in the Central Backend Testing workspace on Slack. This means you are able to make changes locally and see them work without having to flood the main Workspace with messages.
- Messages that are sent in specific channels do so by using the channel's ID. The main workspace and the testing workspace have different channel IDs, so it is necessary to define them both.
- All channel IDs are defined in the file speciic to each Slackbot. For example, in `/util/copy_editing.py` you'll see the line:
    ```
    DI_COPY_TAG_CHANNEL_ID = "XXXXXX" if ENV == "prod" else "YYYYYY"
    ```
  - Here, XXXXXX should re replaced with the channel ID in the main Slack workspace, and YYYYYY should be replace with the channel ID in the Central Backend Testing workspace
- All development should be done in the Central Backend Testing workspace. Once the bot is working, submit a pull request. When the code is pushed to `main`, it will automatically run on the main workspace.

### Finding Channel IDs

- The easiest way to locate a channel ID is by opening Slack in a browser, *not* in the Slack app.
- Navigate to the channel you need the ID for
- The URL should look something like this: `https://app.slack.com/client/TYYYYYY/CXXXXXX`
    - The part beginning with T is the workspace ID. You do not need this.
    - The part beginning with C is the channel ID. The 'C' is part of the ID. It will be followed by a string of numbers and capital letters, and you will need the whole thing.
