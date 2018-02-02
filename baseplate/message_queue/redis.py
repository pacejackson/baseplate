from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import redis

from .base import MessageQueueInterface, TimedOutError


class RedisMessageQueue(MessageQueueInterface):
    """A Redis-backed variant of
    :py:class:`~baseplate.message_queue.base.MessageQueueInterface`.

    :param name: can be any string.

    :param client: should be a :py:class:`redis.ConnectionPool` or
           :py:class:`redis.BlockingConnectionPool` from which a client
           connection can be created from (preferably generated from the
           :py:func:`pool_from_config` helper).

    """
    def __init__(self, name, client):
        self.queue = name
        if isinstance(client, redis.BlockingConnectionPool) or \
                isinstance(client, redis.ConnectionPool):
            self.client = redis.Redis(connection_pool=client)
        else:
            self.client = client

    def get(self, timeout=None):
        """Read a message from the queue.

        :param int timeout: If the queue is empty, the call will block up to
            ``timeout`` seconds or forever if ``None``, if a float is given,
            it will be rounded up to be an integer
        :raises: :py:exc:`TimedOutError` The queue was empty for the allowed
            duration of the call.

        """
        if isinstance(timeout, float):
            timeout = int(ceil(timeout))

        if timeout == 0:
            message = self.client.lpop(self.queue)
        else:
            message = self.client.blpop(self.queue, timeout=timeout)

            if message:
                message = message[1]

        if not message:
            raise TimedOutError

        return message

    def put(self, message, timeout=None):
        """Add a message to the queue.

        :param message: will be typecast to a string upon storage and will come
               out of the queue as a string regardless of what type they are
               when passed into this method.
        """
        return self.client.rpush(self.queue, message)

    def unlink(self):
        """Not implemented for Redis variant
        """
        pass

    def close(self):
        """Close queue when finished

        Will delete the queue from the Redis server (Note, can still enqueue
        and dequeue as the actions will recreate the queue)
        """
        self.client.delete(self.queue)
