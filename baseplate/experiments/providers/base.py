
class ExperimentInterface(object):

    def variant(self, user, content, url_flags):
        raise NotImplementedError

    def should_log_bucketing(self):
        raise NotImplementedError
