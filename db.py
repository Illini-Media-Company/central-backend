from flask_login import UserMixin


users = {}


class User(UserMixin):
    def __init__(self, id_, name, email):
        self.id = id_
        self.name = name
        self.email = email
        users[id_] = self

    @staticmethod
    def get(id_=None):
        print(id_)
        if id_ is None:
            return None
        return users[id_]
