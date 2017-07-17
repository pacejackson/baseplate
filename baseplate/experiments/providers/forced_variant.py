
from .base import ExperimentInterface


class ForcedVariantExperiment(ExperimentInterface):

    def __init__(self, variant):
        self._variant = variant

    def variant(self, *a, **kw):
        return self._variant

    def should_log_bucketing(self):
        return False
