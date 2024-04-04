#!/bin/sh

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements-dev.txt
pre-commit install
gcloud auth application-default login
