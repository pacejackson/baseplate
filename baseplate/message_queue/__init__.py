from .base import MessageQueueError, TimedOutError
from .posix import PosixMessageQueue
from .redis import RedisMessageQueue

MessageQueue = PosixMessageQueue

MAX_MESSAGE_SIZE = 102400
MAX_QUEUE_SIZE = 10000


def message_queue_from_config(app_config, prefix="message_queue.", **kwargs):
    assert prefix.endswith(".")
    config_prefix = prefix[:-1]
    cfg = config.parse_config(app_config, {
        config_prefix: {
            "name": config.String,
            "type": config.OneOf(posix="posix", redis="redis"),
        },
    })
    options = getattr(cfg, config_prefix)

    if options.type == "posix":
        posix_cfg = config.parse_config(app_config, {
            config_prefix: {
                "max_messages": config.Optional(config.Int, default=MAX_QUEUE_SIZE),
                "max_message_size": config.Optional(config.Int, default=MAX_MESSAGE_SIZE),
            },
        })
        posix_options = getattr(cfg, config_prefix)
        return PosixMessageQueue(
            name=name,
            max_messages=posix_options.max_messages,
            max_message_size=posix_options.max_message_size,
        )
    elif options.type == "redis":
        try:
            pool = kwargs['redis_pool']
        except KeyError:
            raise TypeError("message_queue_from_config() missing kwarg 'redis_pool'")
        return RedisMessageQueue(options.name, pool)
