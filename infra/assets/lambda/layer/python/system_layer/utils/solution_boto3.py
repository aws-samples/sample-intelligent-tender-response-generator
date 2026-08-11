"""boto3 client factories that identify calls as coming from this solution.

AWS service API calls made by this solution are attributed to it through a
custom user agent suffix, which the CDK app provides to every function as the
``USER_AGENT_STRING`` environment variable.

Use :func:`get_client` and :func:`get_resource` in place of ``boto3.client``
and ``boto3.resource`` so the suffix is applied consistently. When the variable
is absent (running locally, or in a unit test) the clients are built without it.
"""
import os

import boto3

from botocore.config import Config


def solution_user_agent() -> str:
    """The user agent suffix for this solution, or an empty string if unset."""
    return os.environ.get('USER_AGENT_STRING', '')


def solution_config(config: Config = None, **overrides) -> Config:
    """Return a ``Config`` carrying this solution's user agent suffix.

    An existing ``config`` is preserved: its settings are merged with the user
    agent suffix rather than replaced.
    """
    user_agent = solution_user_agent()

    if user_agent:
        overrides['user_agent_extra'] = user_agent

    solution = Config(**overrides)

    return config.merge(solution) if config is not None else solution


def get_client(service_name: str, config: Config = None, **kwargs):
    """``boto3.client`` carrying this solution's user agent suffix."""
    return boto3.client(service_name, config=solution_config(config), **kwargs)


def get_resource(service_name: str, config: Config = None, **kwargs):
    """``boto3.resource`` carrying this solution's user agent suffix."""
    return boto3.resource(service_name, config=solution_config(config), **kwargs)
