from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class MessageQueueError(Exception):
    """Base exception for message queue related errors."""
    pass


class TimedOutError(MessageQueueError):
    """Raised when a message queue operation times out."""
    def __init__(self):
        super(TimedOutError, self).__init__(
            "Timed out waiting for the message queue.")


class MessageQueueInterface(object):

    def get(self, timeout=None):
        """Read a message from the queue.

        :param float timeout: If the queue is empty, the call will block up to
            ``timeout`` seconds or forever if ``None``.
        :raises: :py:exc:`TimedOutError` The queue was empty for the allowed
            duration of the call.

        """
        raise NotImplementedError()

    def put(self, message, timeout=None):
        """Add a message to the queue.

        :param float timeout: If the queue is full, the call will block up to
            ``timeout`` seconds or forever if ``None``.
        :raises: :py:exc:`TimedOutError` The queue was full for the allowed
            duration of the call.

        """
        raise NotImplementedError()

    def unlink(self):
        """Remove the queue from the system.

        The queue will not leave until the last active user closes it.

        """
        raise NotImplementedError()

    def close(self):
        """Close the queue, freeing related resources.

        This must be called explicitly if queues are created/destroyed on the
        fly. It is not automatically called when the object is reclaimed by
        Python.

        """
        raise NotImplementedError()
