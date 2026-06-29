from aws_cdk.aws_amplify_alpha import (
    GitHubSourceCodeProvider,
    GitLabSourceCodeProvider,
    CodeCommitSourceCodeProvider,
    BasicAuth
)
from aws_cdk.aws_apigateway import CfnUsagePlan
from aws_cdk import aws_lambda as _lambda
from dataclasses import dataclass, field
from typing import Dict, Union, Optional, List


@dataclass
class WebAppPatternProps:
    app_name: str
    user_pool_name: str
    user_pool_domain_prefix: str
    user_pool_client_name: str
    code_provider: Union[
        GitHubSourceCodeProvider,
        GitLabSourceCodeProvider,
        CodeCommitSourceCodeProvider
    ]

    branch_name: str = 'main'
    env_vars: Dict[str, str] = field(default_factory=dict)
    branch_auth: Optional[BasicAuth] = None
    framework_variable_prefix: str = 'REACT_APP'

    api_name: str = 'RestApi'
    api_key_name: str = 'api-key'
    api_allowed_origins: List[str] = field(default_factory=list)
    api_allowed_headers: List[str] = field(default_factory=lambda: [
        "Content-Type", "Authorization", 'x-api-key', 'X-Content-Encoding'
    ])
    api_key_throttle: CfnUsagePlan.ThrottleSettingsProperty = field(
        default_factory=lambda: CfnUsagePlan.ThrottleSettingsProperty(
            rate_limit=10, burst_limit=2
        )
    )

    python_runtime: Optional[_lambda.Runtime] = _lambda.Runtime.PYTHON_3_14
    deploy_test_endpoint: bool = True
