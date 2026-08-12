import jsii

from aws_cdk import IAspect, aws_lambda as _lambda
from constructs import IConstruct


@jsii.implements(IAspect)
class SolutionUserAgentAspect:
    """Identifies this solution's AWS service API calls through a user agent.

    Every Lambda function in the app receives the user agent suffix as the
    ``USER_AGENT_STRING`` environment variable, which the handlers pass to the
    AWS SDK. Applying this as an Aspect keeps the functions themselves free of
    per-function wiring.

    Resources the app creates outside Lambda (the Bedrock AgentCore runtimes)
    take the same variable through their own environment configuration.
    """

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, _lambda.Function):
            node.add_environment('USER_AGENT_STRING', self.user_agent)
