import os

from dotenv import load_dotenv


load_dotenv()
ENV = os.environ.get('ENV', 'dev')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)
