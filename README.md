# central-backend

## Local Setup

### Prerequisites

Make sure you have all of the following installed on your computer:

- Python 3.9 or higher
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
- Git

### Steps

1. Clone this repo on your computer using either GitHub Desktop or the `git` CLI tool.

2. Get the `.env` file from the Managing Editor for Online and place it in `central-backend`.

3. In a terminal window, run the provided script for your OS to set up your development environment.

macOS or Linux:
```
./scripts/setup.sh
```

Windows:
```
.\scripts\setup.bat
```

4. Open a new terminal, and start the Google Cloud Datastore emulator.

```
gcloud beta emulators datastore start
```

5. In your original terminal, run the provided script to start `central-backend` on your computer.

macOS or Linux:
```
./scripts/run.sh
```

Windows:
```
.\scripts\run.bat
```

6. Open your favorite browser and navigate to <https://localhost:5001>. Ignore the "your connection is not private" warning; that's not an issue because no data is sent over the internet, since the server is running on your computer.
