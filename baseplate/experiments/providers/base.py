
class ExperimentInterface(object):

    def __init__(self, id, name, owner, feature_flag=None, enabled=True):
        self.id = id
        self.name = name
        self.owner = owner
        self.feature_flag = None
        self._enabled = enabled

    def enabled(self, **feature_flag_args):
        if not self._enabled:
            return False

        if self.feature_flag is None:
            return True

        if self.feature_flag.enabled(**feature_flag_args):
            return True

    def variant(self, user, content, url_flags):
        raise NotImplementedError

    def should_log_bucketing(self):
        raise NotImplementedError
