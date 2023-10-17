from google.cloud import ndb

from . import client


class IllordleWord(ndb.Model):
    date = ndb.StringProperty()
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
        query = IllordleWord.query(IllordleWord.date == date)
        word = query.get()
        if word is None:
            return None
        return word.to_dict()


def get_all_words():
    with client.context():
        words = [word.to_dict() for word in IllordleWord.query().fetch()]
    return words
