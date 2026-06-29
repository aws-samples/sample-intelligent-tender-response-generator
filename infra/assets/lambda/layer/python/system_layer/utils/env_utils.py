import os

from enum import Enum


class Env(Enum):
    PROD = 'prod'
    DEV = 'dev'


_ENV = Env.PROD


def _is_aws_env() -> bool:
    return 'AWS_LAMBDA_FUNCTION_NAME' in os.environ or 'AWS_EXECUTION_ENV' in os.environ


def _executed_lambda_test() -> bool:
    return 'AWS_LAMBDA_FUNCTION_VERSION' in os.environ and \
        os.environ['AWS_LAMBDA_FUNCTION_VERSION'] == '$LATEST'


def in_dev_environment() -> bool:
    return not _is_aws_env() or _executed_lambda_test()


def _set_env(env: Env) -> None:
    global _ENV
    _ENV = env


def get_env() -> str:
    return _ENV.value


if in_dev_environment():
    _set_env(_ENV.DEV)
else:
    _set_env(_ENV.PROD)