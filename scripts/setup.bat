CALL python3 -m venv .venv
CALL .venv\Scripts\activate.bat
CALL pip install --upgrade -r requirements.txt
CALL pip install --upgrade -r requirements-dev.txt
CALL git config --unset core.hooksPath
CALL pre-commit install
CALL gcloud auth application-default login
