from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .r2 import R2Experiment


class FeatureFlag(R2Experiment):

    def should_log_bucketing(self):
        return False
