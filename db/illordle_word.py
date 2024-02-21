from google.cloud import ndb
from . import client


class IllordleWord(ndb.Model):
    date = ndb.DateProperty()
    word = ndb.StringProperty()
    author = ndb.StringProperty()
    story_url = ndb.StringProperty()
    story_title = ndb.StringProperty()


def add_word(word, date, author, story_url, story_title):
    args = {
        "date": date,
        "word": word,
        "author": author,
        "story_url": story_url,
        "story_title": story_title,
    }
    with client.context():
        query = IllordleWord.query().filter(IllordleWord.date == date)
        illordle_word = query.get()
        if illordle_word is not None:
            args["key"] = illordle_word.key  # replace existing word
        illordle_word = IllordleWord(**args)
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


def get_words_in_date_range(start_date, end_date):
    with client.context():
        if start_date is None and end_date is None:
            return get_all_words()
        elif start_date is None:
            query = IllordleWord.query().filter(IllordleWord.date <= end_date)
        elif end_date is None:
            query = IllordleWord.query().filter(IllordleWord.date >= start_date)
        else:
            query = IllordleWord.query().filter(
                start_date <= IllordleWord.date <= end_date
            )

        words = query.fetch()
        return [w.to_dict() for w in words]


def delete_all_words():
    with client.context():
        words = IllordleWord.query().fetch()
        for w in words:
            w.key.delete()
    return words
