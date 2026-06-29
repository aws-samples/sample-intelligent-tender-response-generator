from aws_cdk import (
    aws_lambda as _lambda
)
from dataclasses import dataclass
from typing import Optional


@dataclass
class WebSocketPatternProps:
    user_pool_id: str
    user_pool_client_id: str

    connections_table_name: str = 'WebSocketConnections'
    api_name: str = 'webSocketApi'
    stage_name: str = 'dev'
    onDefaultHandler: Optional[_lambda.Function] = None

    python_runtime: Optional[_lambda.Runtime] = _lambda.Runtime.PYTHON_3_14
    connections_ttl_hours: str = "14"
    ttl_attr_name: str = 'ExpiresAt'
