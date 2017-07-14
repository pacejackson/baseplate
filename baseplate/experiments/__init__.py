
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from .providers import experiment_from_config
from .providers.legacy import LegacyExperiment
from .._compat import iteritems
from ..context import ContextFactory
from ..events import Event, EventTooLargeError, EventQueueFullError
from ..features import TargetingParams
from ..file_watcher import FileWatcher, WatchedFileNotAvailableError


logger = logging.getLogger(__name__)


class ExperimentsContextFactory(ContextFactory):

    def __init__(self, path, event_queue):
        self._filewatcher = FileWatcher(path, json.load)
        self._event_queue = event_queue

    def make_object_for_context(self, name, server_span):
        return Experiments(self._filewatcher, self._event_queue)


class Experiments(object):

    def __init__(self, config_watcher, event_queue):
        self._config_watcher = config_watcher
        self._event_queue = event_queue
        self._cache = {}

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

    def variant(self, name, session_context):
        if name not in self._cache:
            self._cache[name] = self._bucket(name, session_context)
        return self._cache[name]

    def _bucket(self, name, session_context):
        config = self._get_config(name)
        if not config:
            return None

        experiment = experiment_from_config(config)
        if isinstance(experiment, LegacyExperiment) and experiment.feature:
            targeting = TargetingParams.from_session_context(session_context)
            is_enabled = experiment.feature.is_enabled(
                session_context.user,
                targeting,
            )
            if not is_enabled:
                return None

        variant = experiment.variant(
            user=session_context.user,
            content=session_context.content,
            url_flags=session_context.url_params.get("feature", []),
        )

        should_log_bucketing_event = experiment.should_log_bucketing()

        if variant is None:
            should_log_bucketing_event = False

        if should_log_bucketing_event:
            self._log_bucketing_event(session_context, experiment, variant)

        return variant

    def _log_bucketing_event(self, session_context, experiment, variant):

        if not self._event_queue:
            return

        event_type = "bucket"
        event = Event("bucketing_events", event_type)
        for field, value in iteritems(session_context.event_params()):
            event.set_field(field, value)
        event.set_field("variant", variant)
        event.set_field("experiment_id", experiment.id)
        event.set_field("experiment_name", experiment.name)
        event.set_field("owner", experiment.owner)
        try:
            self._event_queue.put(event)
        except EventTooLargeError:
            logger.exception("That event was too large for event queue.")
        except EventQueueFullError:
            logger.exception("The event queue is full.")


__all__ = ["ExperimentsContextFactory"]
