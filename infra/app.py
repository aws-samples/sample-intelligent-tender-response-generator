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

with open("project_config.json", "r") as file:
    variables = json.load(file)

app = cdk.App()

solution = variables["solution"]

# Apply common tags to all stacks/resources synthesized by this app.
cdk.Tags.of(app).add("auto-delete", "no")
cdk.Tags.of(app).add("auto-stop", "no")

# Identify every resource as belonging to this AWS Solution so deployed
# resources can be attributed back to the solution and its version.
cdk.Tags.of(app).add("Solutions:SolutionID", solution["id"])
cdk.Tags.of(app).add("Solutions:SolutionName", solution["name"])
cdk.Tags.of(app).add("Solutions:SolutionVersion", solution["version"])

env = cdk.Environment(
    account=app.node.try_get_context("account") or os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=app.node.try_get_context("region") or os.environ.get("CDK_DEFAULT_REGION"),
)

core_stack = CoreStack(
    app,
    variables["stacks"]["core_stack_name"],
    env=env
)

frontend_stack = FrontendStack(
    app,
    variables["stacks"]["front_end_stack_name"],
    env=env
)

agentcore_stack = AgentCoreStack(
    app,
    variables["stacks"]["agent_core_stack_name"],
    core_stack,
    env=env
)

infra_stack = InfraStack(
    app,
    variables["stacks"]["infra_stack_name"],
    core_stack=core_stack,
    agentcore_stack=agentcore_stack,
    frontend_stack=frontend_stack,
    env=env
)

agentcore_stack.response_generator_app.grant_invoke(infra_stack.orchestrator_func)
agentcore_stack.document_classifier_app.grant_invoke(infra_stack.orchestrator_func)

Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(reports=True, verbose=True))

app.synth()
