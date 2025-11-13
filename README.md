# Illini Media Console (Central Backend)

The Illini Media Console (or the Central Backend) is one localized app that runs all (or at least most) of IMC's tools and automation workflows. The console can be accessed by anyone with an active @illinimedia.com Google account by visiting [app.dailyillini.com](https://app.dailyillini.com). The frontend is used as a centralize console for all IMC employees to quickly access links, tools and other information.

### Technical Overview

The Central Backend is a [Flask](https://flask.palletsprojects.com/en/stable/) app (which is based on Python). Flask handles all APIs and routing. The frontend is in HTML with [Jinja](https://jinja.palletsprojects.com/en/stable/) as a templating engine. This allows pages (templates) to be rendered with information that comes directly from the backend's database or APIs. Jinja templates are rendered client-side.

The app is deployed to [Google App Engine](https://cloud.google.com/appengine?hl=en) via the [Google Cloud Console](https://console.cloud.google.com). The database is through [Google Datastore](https://cloud.google.com/products/datastore?hl=en), a NoSQL database.


## Getting Started

### IDE (Integrated Development Environment)

Illini Media Company recommends [Visual Studio Code](https://code.visualstudio.com/) — or VSCode — as your primary IDE. Most people are familiar with this as it is free, open-source and has many useful extensions.

**Recommended Extensions**
- [Black Formatter](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter)
    - The repository is already setup to lint Python code using Black to ensure proper formatting. This happens automatically on commits, but you can install this extension to automatically format on file saves.
- [Jinja](https://marketplace.visualstudio.com/items?itemName=wholroyd.jinja)
    - This colorizes Jinja template code which makes viewing easier.
- [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)
    - For code formatting. "Enforces consistent style by parsing your code and re-printing it with its own rules that take the maximum line length into account, wrapping code when necessary."
- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance)
- [Python Debugger](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy)
- [Python Environments](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-python-envs)
- [Code Spell Checker](https://marketplace.visualstudio.com/items?itemName=streetsidesoftware.code-spell-checker)
    - To make sure your code and comments don't have any typos!

### Prerequisites

Make sure you have all of the following:

- Python 3.12 (Different versions may cause issues for Google Cloud)
    - You can check which version you have by running `python --version` or `python3 --version` from a new terminal
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- Git
- [Java 17+](https://www.oracle.com/java/technologies/downloads/#java17)
    - You can check which version you have by running `java --version` from a new terminal
- You've been added to the "IMC Staff - Web Dev" Google Group by your supervisor

### Steps

1. Clone this repo on your computer using either GitHub Desktop or the `git` CLI tool.
    - You can do this by either using the GitHub Desktop application, directly through VSCode, or running the following in a new terminal **inside of the folder/directory where you would like your local copy**:
      ```
      git clone https://github.com/Illini-Media-Company/central-backend
      ```

2. Get the `.env` file from your supervisor and place it in the `central-backend` folder you just cloned.
    - It is crucial that the file is located in the root directory and named `.env` exactly.
    - Note that many of the secrets located in this file are specific to development. On deployment, different secrets may be used.
    - Many API keys are restricted to specific URLs, meaning you will be unable to use them for other projects.

3. Setup Google Cloud CLI
    - In a terminal window, run:
      ```
      gcloud auth login
      ```
    - This will either automatically open a login page on a browser, or you will be given a link to do so.
    - On the page that opens, log in to your **@illinimedia.com** account.
    - Once you have logged in and you are presented with a success screen, close this page then return to the terminal.
    - **Two things can happen from here**, depending on how you installed Google Cloud CLI
        - You're given a message that says:
            ```
            You are now logged in as [{your @illinimedia.com email}].
            Your current project is [central-backend-399421].
            ```
            - In this case, your setup was completed during the initial installation and you are done with this step. You may close this terminal
        - You're met with prompts. Follow them as such:
            - `To continue, you must log in. Would you like to log in (Y/n)?`: Type `Y` then proceed with logging in using your @illinimedia.com account.
            - `Pick cloud project to use` followed by choices: Select the option for `central-backend-399421`.
                - If you do not see this option, it likely means that your supervisor has not yet added you to the required Google Group.
                - Have them do so, then run `gcloud auth login` or `gcloud init` to start the process over.
            - `Which compute zone would you like to use as a project default?`: This does not matter. Choose any option, or do not set a default zone.
    - Once you have completed these steps, you may close this terminal.

4. From a terminal inside of your `central-backend` directory (which is easiest to do by opening a new terminal in VSCode), run the **setup script** for your OS to set up your development environment and install dependencies:

    macOS or Linux:
    ```
    ./scripts/setup.sh
    ```

    Windows:
    ```
    .\scripts\setup.bat
    ```

  > [!NOTE]
  > This process may take a few minutes. Let it run until it is complete. If you are met with any errors (incorrect versions of Python, etc.), address them before you move on.

5. Open a **new** terminal and start the Google Cloud Datastore emulator. *Note that you must leave this terminal running at all times while you are working on the project.*

    ```
    gcloud beta emulators datastore start
    ```
  
  > [!NOTE]
  > You must leave this terminal running at all times while you are working on the project. To ensure you don't accidentally close it, run this in a terminal *not* through VSCode and minimize it.

6. Ensure that your Datastore gave you the following message: `export DATASTORE_EMULATOR_HOST=localhost:8081`
    - If the message does not print *exactly* as above and instead shows a different number, it means one of two things:
        - You have another instance already running in an different terminal. If this is the case, close the one that is not running on `localhost:8081`
        - Another process is running on `localhost:8081` on your computer. Kill/quit that process (Google how to do this if you are unsure). After, return to step 5.
   
7. In the terminal from **step 4**, run the **run script** for your OS to start your local version of `central-backend`:

    macOS or Linux:
    ```
    ./scripts/run.sh
    ```
    
    Windows:
    ```
    .\scripts\run.bat
    ```

8. Open your favorite browser and navigate to <https://127.0.0.1:5001> or whatever URL appears in your terminal underneath the red warning message. Ignore the "your connection is not private" warning; that's not an issue because no data is sent over the internet (the server is running on your computer).

  > [!NOTE]
  > You can ignore the message that will likely pop up saying "your connection is not private." This is not an issue because we're not sending data over the internet and the server is running completely on your computer. On Safari, click "Show Details" > "Visit this website" (in text at the bottom). In Chrome, click "Advanced" > "Proceed to 127.0.0.1 (unsafe)"

### Running After Initial Setup

Once you have completed the setup steps above for the first time, restarting the development server is much easier. **Simply follow steps 5-8**.

### Closing the Server

To stop running the local development server, simply:
  - Terminate the terminal running the server by typing Ctrl + C, then close the window. Do this step first to prevent potential issues.
  - Terminate the terminal running `gcloud` by typing Ctrl + C, then close the window. If you do not terminate first, sometimes it may continue to run in the background and cause future issues (though this is not always the case)

## Slack Apps

Creating, using and running Slack apps (Copy Bot, Breaking News Bot, News Scraper) in development locally. Reference [Slack Documentation]([url](https://docs.slack.dev/tools/bolt-python/building-an-app)) for specific questions about the development process.

### Prerequisites

- Have the Central Backend running locally on your machine
- Receive access to the Central Backend Testing workspace on Slack from your supervisor ([http://onboardingapptesting.slack.com](http://onboardingapptesting.slack.com))

### Implementation

- The file `/util/slackbot.py` defines and creates the main Slack app, called IMC Bot.
  - The same file also defines the IMC Welcome Bot, which is an extension of the IMC Bot app and is responsible for sending welcome messages to everyone added to the workspace and routing them to the correct channels.
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
- All channel IDs are defined in the file specific to each Slackbot. For example, in `/util/copy_editing.py` you'll see the line:
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
