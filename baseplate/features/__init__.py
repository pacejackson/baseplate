
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from collections import namedtuple

from .feature import feature_flag_from_config
from ..file_watcher import FileWatcher, WatchedFileNotAvailableError
from ..context import ContextFactory


logger = logging.getLogger(__name__)


class User(object):

    def __init__(self, id, name, created, flags=None):
        self.id = id
        self.name = name
        self.created = created
        self.flags = flags or set()

    @property
    def logged_in(self):
        return self.name is not None


Content = namedtuple("Content", ["id", "type"])


class FeatureFlagsContextFactory(ContextFactory):
    """ ContextFactory for FeatureFlags.

    This factory will attach a :py:class:`baseplate.features.FeatureFlags`
    object on the :term:`context object` that will use the config file
    specified by the given path.  Uses a :py:class:`baseplate.file_watcher.FileWatcher`
    object to serve the config file so you will be sure to always have the
    current version.
    """
    def __init__(self, path):
        self._filewatcher = FileWatcher(path, json.load)

    def make_object_for_context(self, name, server_span):
        return FeatureFlags(self._filewatcher)


class FeatureFlags(object):
    """Access to feature flags with automatic config updates when changed."""

    def __init__(self, config_watcher):
        self._config_watcher = config_watcher

    def _get_config(self, name):
        try:
            config_data = self._config_watcher.get_data()
            return config_data[name]
        except WatchedFileNotAvailableError:
            logger.warning("Experiment config file not found")
            return
        except KeyError:
            logger.warning(
                "Experiment <%r> not found in experiment config",
                name,
            )
            return
        except TypeError:
            logger.warning("Could not load experiment config: %r", name)
            return

    def enabled(self, name, **args):
        """ Check if the feature flag with the given name is enabled for the
        provider user and targeting parameters.

        :param str name: The name of the feature flag that you want to check.
        :param baseplate.features.SessionContext session_context: The current
        session context.  This contains information about the user and request
        that may be used in determining if a feature should be enabled.

        :rtype: :py:class:`bool`
        """
        config = self._get_config(name)
        if not config:
            return False
        feature = feature_flag_from_config(config)
        return feature.enabled(name, **args)


__all__ = ["FeatureFlagsContextFactory"]
