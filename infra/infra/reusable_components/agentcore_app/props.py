from aws_cdk import (
    aws_codebuild as codebuild,
    aws_dynamodb as ddb,
    aws_sqs as sqs,
    aws_lambda as _lambda,
)

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class AgentCoreAppPatternProps:
    agent_runtime_name: str
    source_code_path: str

    agent_runtime_environment_variables: Dict[str, str] = field(default_factory=dict)
    agent_runtime_network_mode: Optional[str] = 'PUBLIC'

    codebuild_environment: codebuild.BuildEnvironment = field(default_factory=lambda: codebuild.BuildEnvironment(
        build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
        compute_type=codebuild.ComputeType.LARGE,
        privileged=True,
    ))

    python_runtime: Optional[_lambda.Runtime] = _lambda.Runtime.PYTHON_3_14
    image_tag: Optional[str] = 'latest'

    runtime_invocations_table: Optional[ddb.Table] = None
    runtime_invocations_queue: Optional[sqs.Queue] = None
    runtime_invocations_consumer: Optional[_lambda.Function] = None

    runtime_invocations_table_name: str = 'RuntimeInvocations'
    runtime_invocations_queue_name: str = 'RuntimeInvocationsQueue'
    runtime_invocations_consumer_name: str = 'runtimeInvocationsQueueConsumer'

    runtime_invocations_ttl_days: str = "14"
    ttl_attr_name: str = 'ExpiresAt'
    partition_key_attr_name: str = 'Id'
