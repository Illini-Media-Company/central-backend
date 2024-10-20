# central-backend

[app.dailyillini.com](https://app.dailyillini.com)

## Local Setup

### Prerequisites

Make sure you have all of the following installed on your computer:

- Python 3.9 or higher
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- Git
- [Java 11+](https://www.oracle.com/java/technologies/downloads/#java17) (check if you have it already by running `java --version` in a terminal)

### Steps

1. Clone this repo on your computer using either GitHub Desktop or the `git` CLI tool.

2. Get the `.env` file from the Lead Developer and place it in the `central-backend` folder you just cloned.

3. In a terminal window, run `gcloud auth login` to open a login page on your browser. Log in to your **@illinimedia.com** account, then return to the terminal. Following the prompt, set the current project to `central-backend-399421`.

4. Run the provided script for your OS to set up your development environment.
```
macOS or Linux:
```
./scripts/setup.sh
```

```
Windows:
```
.\scripts\setup.bat
```

5. Open a new terminal, and start the Google Cloud Datastore emulator.
gcloud beta emulators datastore start

You would see something sililar to:
[datastore] API endpoint: http://[::1]:8532
[datastore] If you are using a library that supports the DATASTORE_EMULATOR_HOST environment variable, run:
[datastore] 
[datastore]   export DATASTORE_EMULATOR_HOST=[::1]:8532

6. Stop the Current Datastore Emulator by pressing CTRL+C

7. Start the Datastore Emulator with IPv4 Only:
gcloud beta emulators datastore start --host-port=localhost:8532

8. Set the Environment Variable for the Emulator
export DATASTORE_EMULATOR_HOST=localhost:8532

9. Verify Emulator is Running
curl http://localhost:8532

10. In your original terminal, run the provided script to start Your Flask Application:
macOS or Linux:
```
./scripts/run.sh
```

Windows:
```
.\scripts\run.bat
```

11. Open your favorite browser and navigate to <https://localhost:5001>. Ignore the "your connection is not private" warning; that's not an issue because no data is sent over the internet (the server is running on your computer).

###

