#!/usr/bin/env python3
import os
import aws_cdk as cdk
import json
import cdk_nag
from aws_cdk import Aspects

from infra.agentcore_stack import AgentCoreStack
from infra.core_stack import CoreStack
from infra.frontend_stack import FrontendStack
from infra.infra_stack import InfraStack
from infra.reusable_components import SolutionUserAgentAspect

with open("project_config.json", "r") as file:
    variables = json.load(file)

app = cdk.App()

solution = variables["solution"]

# Apply common tags to all stacks/resources synthesized by this app.
cdk.Tags.of(app).add("auto-delete", "no")
cdk.Tags.of(app).add("auto-stop", "no")

# Identify the AWS service API calls this solution makes, so its API usage can
# be attributed to the solution and its version.
user_agent = f"AWSSOLUTION/{solution['id']}/{solution['version']}"


def solution_description(component: str) -> str:
    """Build a stack description carrying the solution identifier.

    Deployments of this solution are counted by matching the solution id in the
    description of each deployed CloudFormation stack, so every stack below
    carries one. The component name distinguishes the stacks from each other.
    """
    return (f"({solution['id']}) - {solution['name']} - {component}. "
            f"Version {solution['version']}")


env = cdk.Environment(
    account=app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION"),
)

core_stack = CoreStack(
    app,
    variables["stacks"]["core_stack_name"],
    description=solution_description("document storage"),
    env=env
)

frontend_stack = FrontendStack(
    app,
    variables["stacks"]["front_end_stack_name"],
    description=solution_description("web application"),
    env=env
)

agentcore_stack = AgentCoreStack(
    app,
    variables["stacks"]["agent_core_stack_name"],
    core_stack,
    user_agent=user_agent,
    description=solution_description("agent runtimes"),
    env=env
)

infra_stack = InfraStack(
    app,
    variables["stacks"]["infra_stack_name"],
    core_stack=core_stack,
    agentcore_stack=agentcore_stack,
    frontend_stack=frontend_stack,
    description=solution_description("analysis workflow"),
    env=env
)

agentcore_stack.response_generator_app.grant_invoke(infra_stack.orchestrator_func)
agentcore_stack.document_classifier_app.grant_invoke(infra_stack.orchestrator_func)

Aspects.of(app).add(SolutionUserAgentAspect(user_agent))

Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(reports=True, verbose=True))

app.synth()
