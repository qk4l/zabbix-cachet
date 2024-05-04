import logging

logger = logging.getLogger(__name__)


class ZabbixCachetException(Exception):
    def __init__(self, message=None, errors=None):
        if errors:
            message = ', '.join(errors)
        self.errors = errors
        if message:
            logger.error(repr(message).rstrip())
        super(Exception, self).__init__(message)


class InvalidConfig(ZabbixCachetException):
    pass

class CachetApiException(ZabbixCachetException):
    pass

class ZabbixNotAvailable(ZabbixCachetException):
    pass