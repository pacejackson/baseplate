from .base import MessageQueueError, TimedOutError
from .posix import PosixMessageQueue
from .redis import RedisMessageQueue

MessageQueue = PosixMessageQueue

MAX_MESSAGE_SIZE = 102400
MAX_QUEUE_SIZE = 10000


def message_queue_from_config(app_config, prefix="message_queue.", name=None):
    assert prefix.endswith(".")
    config_prefix = prefix[:-1]
    cfg = config.parse_config(app_config, {
        config_prefix: {
            "name": config.Optional(config.String, default=None),
            "type": config.OneOf(posix="posix", redis="redis"),
        },
    })
    options = getattr(cfg, config_prefix)
    name = name or options.name
    if name is None:
        raise TypeError("No 'name' specified for message_queue_from_config()")

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
        from ..context.redis import redis_pool_from_config
        pool = redis_pool_from_config(app_config, prefix="message_queue_redis.")
        return RedisMessageQueue(options.name, pool)
