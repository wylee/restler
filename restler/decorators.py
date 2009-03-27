import logging

from decorator import decorator


log = logging.getLogger(__name__)


@decorator
def privileged(method, self, *args, **kwargs):
    log.debug(
        'Default `privileged` decorator does NOT check privileges. '
        'It only calls the original method.')
    return method(self, *args, **kwargs)
