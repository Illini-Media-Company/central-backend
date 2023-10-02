from flask_login import UserMixin
from google.cloud import ndb

from . import client


class IllordleWord(ndb.Model):
    date = ndb.DateProperty()
    word = ndb.StringProperty()


def add_word(word, date):
    with client.context():
        illordle_word = IllordleWord.query().filter(IllordleWord.date == date)
        if illordle_word is not None:
            illordle_word.key.delete()
        illordle_word = IllordleWord(date=date, word=word)
        illordle_word.put()

    return illordle_word


def get_word(date):
    with client.context():
        illordle_word = IllordleWord.query().filter(IllordleWord.date == date)

    return illordle_word
