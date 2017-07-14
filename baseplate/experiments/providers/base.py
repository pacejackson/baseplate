
class ExperimentInterface(object):

    def __init__(self, id, name, owner):
        self.id = id
        self.name = name
        self.owner = owner

    def variant(self, user, content, url_flags):
        raise NotImplementedError

    def should_log_bucketing(self):
        raise NotImplementedError
