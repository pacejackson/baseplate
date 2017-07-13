
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from .feature import feature_flag_from_config
from ..file_watcher import FileWatcher, WatchedFileNotAvailableError
from ..context import ContextFactory


logger = logging.getLogger(__name__)


class OauthClient(object):

    def __init__(self, id):
        self.id = id


class TargetingParams(object):

    def __init__(self, url_features=None, subreddit=None, subdomain=None,
                 oauth_client=None):
        self.url_features = url_features or []
        self.subreddit = subreddit
        self.subdomain = subdomain
        self.oauth_client = oauth_client


class Content(object):

    def __init__(self, id, type):
        self.id = id
        self.type = type


class User(object):

    def __init__(self, id, name, created, flags=None, event_baggage=None):
        self.id = id
        self.name = name
        self.created = created
        self.flags = flags or set()
        self.event_baggage = event_baggage or {}

    @property
    def logged_in(self):
        return self.name is not None

    @property
    def id36(self):
        return self.id[3:]


class FeatureFlagsContextFactory(ContextFactory):

    def __init__(self, path):
        self._filewatcher = FileWatcher(path, json.load)

    def make_object_for_context(self, name, server_span):
        return FeatureFlags(self._filewatcher)


class FeatureFlags(object):

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

    def enabled(self, name, user, targeting):
        config = self._get_config(name)
        if not config:
            return False
        feature = feature_flag_from_config(config)
        return feature.enabled(name, user, targeting)


__all__ = ["FeatureFlagsContextFactory"]
