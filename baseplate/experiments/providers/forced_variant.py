
from .base import ExperimentInterface


class ForcedVariantExperiment(ExperimentInterface):

    def __init__(self, id, name, owner, forced_variant):
        super(ForcedVariantExperiment, self).__init__(id, name, owner)
        self._variant = forced_variant

    def variant(self, *a, **kw):
        return self._variant

    def should_log_bucketing(self):
        return False
