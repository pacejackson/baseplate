
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


UrlComponents = namedtuple(
    "UrlComponents",
    ["params", "subdomain", "subreddit_name", "content_id", "content_type"],
)


def parse_url(url):
    subdomain = None
    subreddit = None
    content_id = None
    content_type = None
    params = None
    return UrlComponents(
        params=params,
        subdomain=subdomain,
        subreddit_name=subreddit,
        content_id=content_id,
        content_type=content_type,
    )


class User(object):

    def __init__(self, id, name, created, flags=None):
        self.id = id
        self.name = name
        self.created = created
        self.flags = flags or set()

    @property
    def logged_in(self):
        return self.name is not None

    @property
    def id36(self):
        return self.id[3:]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created": self.created,
            "flags": self.flags,
        }

    def event_params(self):
        event_params = {}
        if self.logged_in:
            event_params["user_id"] = self.id
            event_params["user_name"] = self.name
        else:
            event_params["loid"] = self.id
            event_params["loid_created"] = self.created
        return event_params


class SessionContext(object):

    def __init__(self, session_id, user, url=None, oauth_client_id=None,
                 baggage=None):
        self.session_id = session_id
        self.user = user
        self.oauth_client_id = oauth_client_id
        self._baggage = baggage
        self._url = url
        self._url_properties = None

    def _get_url_property(self, name):
        if self._url_properties is None:
            self._url_properties = {}
            components = parse_url(self._url)
            self._url_properties["url_params"] = components.params or {}
            self._url_properties["subdomain"] = components.subdomain
            self._url_properties["subreddit"] = components.subreddit_name
            self._url_properties["content"] = Content(
                components.content_id,
                components.content_type,
            )
        return self._url_properties[name]

    @property
    def subreddit(self):
        return self._get_url_property("subreddit")

    @property
    def content(self):
        return self._get_url_property("content")

    @property
    def subdomain(self):
        return self._get_url_property("subdomain")

    @property
    def url_params(self):
        return self._get_url_property("url_params")

    def set_baggage(self, key, value):
        self._baggage[key] = value

    def to_dict(self):
        return {
            "user": self.user.to_dict(),
            "url": self._url,
            "oauth_client_id": self.oauth_client_id,
            "baggage": self._baggage,
        }

    def event_params(self):
        event_params = {}
        if self.session_id:
            event_params["session_id"] = self.session_id
        if self._url:
            event_params["request_url"] = self._url
        if self.oauth_client_id:
            event_params["oauth_client_id"] = self.oauth_client_id
        if self._baggage:
            event_params.update(self._baggage)
        if self.user:
            event_params.update(self.user.event_params())
        return event_params


class TargetingParams(object):

    def __init__(self, url_features=None, subreddit=None, subdomain=None,
                 oauth_client=None):
        self.url_features = url_features or []
        self.subreddit = subreddit
        self.subdomain = subdomain
        self.oauth_client = oauth_client

    @classmethod
    def from_session_context(cls, session_context):
        url_features = None
        url_params = session_context.url_params
        if url_params and "feature" in url_params:
            url_features = url_params["feature"]
        return cls(
            url_features=url_features,
            subreddit=session_context.subreddit,
            subdomain=session_context.subdomain,
            oauth_client=session_context.oauth_client_id,
        )


class Content(object):

    def __init__(self, id, type):
        self.id = id
        self.type = type


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

    def enabled(self, name, session_context):
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
        targeting = TargetingParams.from_session_context(session_context)
        return feature.enabled(name, session_context.user, targeting)


__all__ = ["FeatureFlagsContextFactory"]
