import requests
from requests.auth import HTTPBasicAuth

from util.constants import (
    SNO_ADMIN_USERNAME,
    SNO_ADMIN_PASSWORD
)


DAILY_ILLINI_URL = 'https://dailyillini.com'


def setup_user(name, email, groups):
    auth = HTTPBasicAuth(SNO_ADMIN_USERNAME, SNO_ADMIN_PASSWORD)
    user_data = requests.get(DAILY_ILLINI_URL + f'/wp-json/wp/v2/users?search={email}', auth=auth)
    print('SNO user:')
    print(user_data.content)
