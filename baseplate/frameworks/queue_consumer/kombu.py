import logging
import queue
import socket

from typing import Callable
from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING

import kombu

from gevent.server import StreamServer
from kombu.mixins import ConsumerMixin
from kombu.transport.virtual import Channel

from baseplate import Baseplate
from baseplate import RequestContext
from baseplate.clients.kombu import KombuSerializer
from baseplate.server.queue_consumer import HealthcheckCallback
from baseplate.server.queue_consumer import make_simple_healthchecker
from baseplate.server.queue_consumer import MessageHandler
from baseplate.server.queue_consumer import PumpWorker
from baseplate.server.queue_consumer import QueueConsumerFactory


if TYPE_CHECKING:
    WorkQueue = queue.Queue[kombu.Message]  # pylint: disable=unsubscriptable-object
else:
    WorkQueue = queue.Queue


logger = logging.getLogger(__name__)


Handler = Callable[[RequestContext, kombu.Message], None]


class FatalMessageHandlerError(Exception):
    """An error that signals that the queue process should exit.

    Raising an Exception that is a subclass of FatalMessageHandlerError will
    cause the KombuMessageHandler to re-raise the exception rather than swallowing
    it which will cause the handler thread/process to stop.  This, in turn, will
    gracefully shut down the QueueConsumerServer currently running.

    Exceptions of this nature should be reserved for errors that are due to
    problems with the environment rather than the message itself.  For example,
    a node that cannot get its AWS credentials.
    """


class KombuConsumerWorker(ConsumerMixin, PumpWorker):
    """Consumes messages from the given queues and pumps them into the internal work_queue.

    This class does not directly implement the abstract `run` command from
    PumpWorker because the ConsumerMixin class already defines it.
    """

    def __init__(
        self,
        connection: kombu.Connection,
        queues: Sequence[kombu.Queue],
        work_queue: WorkQueue,
        serializer: Optional[KombuSerializer] = None,
    ):
        self.connection = connection
        self.queues = queues
        self.work_queue = work_queue
        self.serializer = serializer

    def get_consumers(self, Consumer: kombu.Consumer, channel: Channel) -> Sequence[kombu.Consumer]:
        args = dict(queues=self.queues, on_message=self.work_queue.put)
        if self.serializer:
            args["accept"] = [self.serializer.name]
        return [Consumer(**args)]

    def stop(self) -> None:
        logger.debug("Closing KombuConsumerWorker.")
        # `should_stop` is an attribute of `ConsumerMixin`
        self.should_stop = True


class KombuMessageHandler(MessageHandler):
    def __init__(self, baseplate: Baseplate, name: str, handler_fn: Handler):
        self.baseplate = baseplate
        self.name = name
        self.handler_fn = handler_fn

    def handle(self, message: kombu.Message) -> None:
        context = self.baseplate.make_context_object()
        try:
            # We place the call to ``baseplate.make_server_span`` inside the
            # try/except block because we still want Baseplate to see and
            # handle the error (publish it to error reporting)
            with self.baseplate.make_server_span(context, self.name) as span:
                delivery_info = message.delivery_info
                span.set_tag("kind", "consumer")
                span.set_tag("amqp.routing_key", delivery_info.get("routing_key", ""))
                span.set_tag("amqp.consumer_tag", delivery_info.get("consumer_tag", ""))
                span.set_tag("amqp.delivery_tag", delivery_info.get("delivery_tag", ""))
                span.set_tag("amqp.exchange", delivery_info.get("exchange", ""))
                self.handler_fn(context, message)
        except Exception as exc:
            logger.exception(
                "Unhandled error while trying to process a message.  The message "
                "has been returned to the queue broker."
            )
            message.requeue()
            if isinstance(exc, FatalMessageHandlerError):
                logger.info("Recieved a fatal error, terminating the server.")
                raise
        else:
            message.ack()


class KombuQueueConsumerFactory(QueueConsumerFactory):
    def __init__(
        self,
        baseplate: Baseplate,
        name: str,
        connection: kombu.Connection,
        queues: Sequence[kombu.Queue],
        handler_fn: Handler,
        health_check_fn: Optional[HealthcheckCallback] = None,
        serializer: Optional[KombuSerializer] = None,
    ):
        self.baseplate = baseplate
        self.connection = connection
        self.queues = queues
        self.name = name
        self.handler_fn = handler_fn
        self.health_check_fn = health_check_fn
        self.serializer = serializer

    @classmethod
    def new(
        cls,
        baseplate: Baseplate,
        exchange: kombu.Exchange,
        connection: kombu.Connection,
        queue_name: str,
        routing_keys: Sequence[str],
        handler_fn: Handler,
        health_check_fn: Optional[HealthcheckCallback] = None,
        serializer: Optional[KombuSerializer] = None,
    ) -> "KombuQueueConsumerFactory":
        queues = []
        for routing_key in routing_keys:
            queues.append(kombu.Queue(name=queue_name, exchange=exchange, routing_key=routing_key))
        return cls(
            baseplate=baseplate,
            name=queue_name,
            connection=connection,
            queues=queues,
            handler_fn=handler_fn,
            health_check_fn=health_check_fn,
            serializer=serializer,
        )

    def build_pump_worker(self, work_queue: WorkQueue) -> KombuConsumerWorker:
        return KombuConsumerWorker(
            connection=self.connection,
            queues=self.queues,
            work_queue=work_queue,
            serializer=self.serializer,
        )

    def build_message_handler(self) -> KombuMessageHandler:
        return KombuMessageHandler(self.baseplate, self.name, self.handler_fn)

    def build_health_checker(self, listener: socket.socket) -> StreamServer:
        return make_simple_healthchecker(listener, callback=self.health_check_fn)
