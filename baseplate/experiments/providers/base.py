from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class BaseExperimentProvider(object):
    """Base interface for experiment objects. """

    def get_variant(self):
        """Determine which variant, if any, of this experiment is active.

        All arguments needed for bucketing, targeting, and variant overrides
        should be passed in as kwargs.  The parameter names are determined by
        the specific implementation of the Experiment interface.

        :rtype: :py:class:`str`
        :returns: The name of the enabled variant as a string if any variant is
        enabled.  If no variant is enabled, return None.
        """
        raise NotImplementedError

    def get_unique_id(self):
        raise NotImplementedError
