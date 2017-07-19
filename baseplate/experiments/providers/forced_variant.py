
from .base import ExperimentInterface


class ForcedVariantExperiment(ExperimentInterface):
    """ An experiment that always returns a specified variant.  Should not log
    bucketing events to the event pipeline.
    """

    def __init__(self, variant):
        self._variant = variant

    def variant(self, **kwargs):
        return self._variant

    def should_log_bucketing(self):
        return False
