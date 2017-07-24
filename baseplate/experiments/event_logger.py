from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from .._compat import iteritems
from ..events import Event, EventTooLargeError, EventQueueFullError

logger = logging.getLogger(__name__)


class BaseEventLogger(object):

    def log_event(self, topic, type, **fields):
        raise NotImplementedError


class NullEventLogger(BaseEventLogger):

    def log_event(self, topic, type, **fields):
        pass


class EventQueueLogger(BaseEventLogger):

    def __init__(self, context_name, server_span, event_queue):
        self._context_name = context_name
        self._span = server_span
        self._event_queue = event_queue

    def log_event(self, topic, type, **fields):
        event = Event(topic, type)
        for field, value in iteritems(fields):
            event.set_field(field, value)

        event.set_field("request_id", self._span.trace_id)
        span_name = "{}.{}".format(self._context_name, "events")
        with self._span.make_child(span_name) as child_span:
            try:
                self._event_queue.put(event)
            except EventTooLargeError as exc:
                logger.warning(
                    "The event payload was too large for the event queue."
                )
                child_span.set_tag("error", True)
                child_span.log("error.object", exc)
            except EventQueueFullError as exc:
                logger.warning("The event queue is full.")
                child_span.set_tag("error", True)
                child_span.log("error.object", exc)
