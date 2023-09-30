CALL .venv\Scripts\activate.bat
CALL gcloud beta emulators datastore env-init > set_vars.cmd
CALL set_vars.cmd
CALL python main.py
