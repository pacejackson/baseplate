from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .base import BaseExperimentProvider


class ForcedVariantExperiment(BaseExperimentProvider):
    """An experiment that always returns a specified variant.

    Should not log bucketing events to the event pipeline.  Note that
    ForcedVariantExperiments are not directly configured, rather they are
    used when an experiment is disabled or when "global_override" is set in
    the base config.
    """

    def __init__(self, variant):
        self._variant = variant

    def get_variant(self):
        return self._variant

    def get_unique_id(self):
        return str(self._variant).lower()
