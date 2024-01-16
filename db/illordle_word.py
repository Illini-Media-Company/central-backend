from google.cloud import ndb
from . import client
import datetime


class IllordleWord(ndb.Model):
    date = ndb.DateProperty()
    word = ndb.StringProperty()


def add_word(word, date):
    with client.context():
        query = IllordleWord.query().filter(IllordleWord.date == date)
        illordle_word = query.get()
        if illordle_word is not None:
            illordle_word.key.delete()
        illordle_word = IllordleWord(date=date, word=word)
        illordle_word.put()
        return illordle_word.to_dict()


def get_word(date):
    with client.context():
        query = IllordleWord.query().filter(IllordleWord.date == date)
        illordle_word = query.get()
        if illordle_word is not None:
            return illordle_word.to_dict()
        else:
            return None


def get_all_words():
    with client.context():
        query = IllordleWord.query()
        words = query.fetch()
        return [w.to_dict() for w in words]


def delete_all_words():
    with client.context():
        words = IllordleWord.query().fetch()
        for w in words:
            w.key.delete()
    return words
