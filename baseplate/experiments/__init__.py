from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from .providers import parse_experiment
from .._compat import iteritems
from ..context import ContextFactory
from ..events import Event, EventTooLargeError, EventQueueFullError
from ..file_watcher import FileWatcher, WatchedFileNotAvailableError


logger = logging.getLogger(__name__)


class ExperimentsContextFactory(ContextFactory):

    def __init__(self, path, event_queue):
        self._filewatcher = FileWatcher(path, json.load)
        self._event_queue = event_queue

    def make_object_for_context(self, name, server_span):
        return Experiments(self._filewatcher, self._event_queue)


class Experiments(object):

    def __init__(self, config_watcher, event_queue=None):
        self._config_watcher = config_watcher
        self._event_queue = event_queue
        self._already_bucketed = set()

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

    def variant(self, name, bucketing_event_override=None,
                extra_event_params=None, **kwargs):
        config = self._get_config(name)
        if not config:
            return None

        experiment = parse_experiment(config)
        variant = experiment.variant(**kwargs)

        should_log_bucketing_event = experiment.should_log_bucketing()

        cache_key = experiment.event_cache_key(**kwargs)

        if variant is None:
            should_log_bucketing_event = False

        if cache_key and cache_key in self._already_bucketed:
            should_log_bucketing_event = False

        if bucketing_event_override is True:
            should_log_bucketing_event = True
        elif bucketing_event_override is False:
            should_log_bucketing_event = False

        if should_log_bucketing_event:
            self._log_bucketing_event(experiment, variant, extra_event_params)
            if cache_key:
                self._already_bucketed.add(cache_key)

        return variant

    def _log_bucketing_event(self, experiment, variant, extra_event_params=None):

        if not self._event_queue:
            return

        extra_event_params = extra_event_params or {}

        event_type = "bucket"
        event = Event("bucketing_events", event_type)
        for field, value in iteritems(extra_event_params):
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
