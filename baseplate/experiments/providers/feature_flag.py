from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .r2 import R2Experiment


class FeatureFlag(R2Experiment):
    """ An experiment with a single variant "active" that does not log
    bucketing events to the event pipeline.  Use this type of experiment if
    you just want to controll access to a feature but do not want to run an
    actual experiment.  For example:

    1. Slowly rolling out a new feature to a % of users
    2. Restricting a new feature to certain subreddits
    """

    def should_log_bucketing(self):
        return False