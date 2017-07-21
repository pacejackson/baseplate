from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class Experiment(object):
    """ Base interface for experiment objects. """

    def event_cache_key(self, **kwargs):
        return None

    def variant(self, **kwargs):
        """ Determine which variant, if any, of this experiment is active.



        :rtype string:
        :returns: The name of the enabled variant as a string if any variant is
        enabled.  If no variant is enabled, return None.
        """
        raise NotImplementedError

    def should_log_bucketing(self):
        """Should this experiment log bucketing events to the event pipeline.
        """
        raise NotImplementedError
