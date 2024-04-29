#!/bin/sh

source .venv/bin/activate
$(gcloud beta emulators datastore env-init)
python main.py
