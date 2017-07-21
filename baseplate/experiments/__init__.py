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
    """ Experiment manager context factory

    This factory will attach a new :py:class:`baseplate.experiments.Experiments`
    to an attribute on the :term:`context object`.
    """
    def __init__(self, path, event_queue):
        """ ExperimentContextFactory constructor

        :param str path: Path to the experiment config file.
        :param baseplate.events.EventQueue event_queue: Event queue used for
            logging bucketing events to the event pipeline.  You can set this
            to None to disabled bucketing events entirely.
        """
        self._filewatcher = FileWatcher(path, json.load)
        self._event_queue = event_queue

    def make_object_for_context(self, name, server_span):
        return Experiments(self._filewatcher, self._event_queue)


class Experiments(object):
    """ Access to experiments with automatic refresh when changed. Handles
    logging bucketing events to the event pipeline.
    """

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
        """ Which variant, if any, is active for the experiment specified by
        "name".  If a variant is active, a bucketing event will be logged to
        the event pipeline unless any one of the following conditions are met:

        1. bucketing_event_override is set to False.
        2. The experiment specified by "name" explicitly disables bucketing
           events.
        3. We have already logged a bucketing event for the value specified by
           experiment.event_cache_key(**kwargs) within the current session.

        :param str name: Name of the experiment you want to run.
        :param bool bucketing_event_override: Optional value, defaults to None.
            If set to True, will always log bucketing events unless the
            experiment explicitly disables them.  If set to False, will never
            send a bucketing event.  If set to None, no override will be
            applied.
        :param dict extra_event_params: Optional value.  Any extra values you
            want to add to the bucketing event.
        :param kwargs:  Arguments that will be passed to experiment.variant to
            determine bucketing, targeting, and overrides.

        :rtype str:
        :return: Variant name if a variant is active, None otherwise.
        """
        config = self._get_config(name)
        if not config:
            return None

        experiment = parse_experiment(config)
        variant = experiment.variant(**kwargs)

        do_log = True

        if variant is None:
            do_log = False

        cache_key = experiment.event_cache_key(**kwargs)

        if cache_key and cache_key in self._already_bucketed:
            do_log = False

        if bucketing_event_override is True:
            do_log = True
        elif bucketing_event_override is False:
            do_log = False

        do_log = do_log and experiment.should_log_bucketing()

        if do_log:
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
