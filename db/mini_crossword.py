from datetime import date
from google.cloud import ndb
from . import client


class MiniCrossword(ndb.Model):
    id = ndb.IntegerProperty()
    date = ndb.DateProperty()
    grid = ndb.JsonProperty()
    clues = ndb.JsonProperty()
    answers = ndb.JsonProperty()
    origin = ndb.StringProperty()  # "manual" or "auto" origin
    article_link = ndb.StringProperty()
    created_by = ndb.StringProperty()
    created_at = ndb.DateTimeProperty(auto_now_add=True)


# add new crossword to datastore
def add_crossword(id, date, grid, clues, answers, origin, article_link, created_by):
    with client.context():
        crossword = MiniCrossword(
            id=id,
            date=date,
            grid=grid,
            clues=clues,
            answers=answers,
            origin=origin,
            article_link=article_link,
            created_by=created_by,
        )
        crossword.put()
    return crossword.to_dict()


# return crossword by date
def get_crossword(date):
    with client.context():
        query = MiniCrossword.query().filter(MiniCrossword.date == date)
        crossword = query.get()
        if crossword:
            return crossword.to_dict()  # found
        else:
            return None


# All crosswords
def get_all_crosswords():
    with client.context():
        crosswords = MiniCrossword.query().order(-MiniCrossword.created_at).fetch()
        return [cw.to_dict() for cw in crosswords]


# Delete all crossword entries
def delete_all_crosswords():
    with client.context():
        crosswords = MiniCrossword.query().fetch()
        for cw in crosswords:
            cw.key.delete()
    return "All crosswords deleted"
