#!/bin/sh

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements-dev.txt
gcloud auth application-default login
