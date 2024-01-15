#!/bin/sh

source .venv/bin/activate
git config --local core.hooksPath .githooks/
$(gcloud beta emulators datastore env-init)
python main.py
