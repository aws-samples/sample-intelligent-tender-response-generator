import json
import logging

from http import HTTPStatus
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(logging.ERROR)


class RequestError(Exception):
    def __init__(self, msg: str, code: int):
        super().__init__(msg)
        self._msg = msg
        self._code = code

    def __repr__(self):
        return {
            'body': json.dumps({'Message': self._msg, 'Code': self._code}),
            'statusCode': self._code
        }

    def __str__(self):
        return str(self.__repr__())

    @classmethod
    def not_found(cls):
        return RequestError('The requested resource was not found', HTTPStatus.NOT_FOUND)

    @classmethod
    def not_implemented(cls):
        return RequestError('This operation is not supported', HTTPStatus.NOT_IMPLEMENTED)

    @classmethod
    def forbidden(cls):
        return RequestError("You don't have permission to access this resource", HTTPStatus.FORBIDDEN)


def __handle_errors(func, *args, **kwargs):
    try:
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            raise RequestError(e.args[0], HTTPStatus.BAD_REQUEST)
        except RequestError as e:
            raise e
        except Exception as e:
            raise RequestError(e.args[0], HTTPStatus.INTERNAL_SERVER_ERROR)
    except RequestError as e:
        raise e


def error_handler(func):
    def inner_function(*args, **kwargs):
        try:
            return __handle_errors(func, *args, **kwargs)
        except RequestError as e:
            logger.exception(json.dumps(e.__repr__()))
            return e.__repr__()

    return inner_function
