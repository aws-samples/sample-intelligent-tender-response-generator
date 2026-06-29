from aws_cdk import (
    Stack,
    aws_iam as iam,
)
from constructs import Construct
from .reusable_components import *
from cdk_nag import NagSuppressions


class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, core_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.response_generator_app = AgentCoreAppPattern(
            self, 'ResponseGeneratorApp',
            AgentCoreAppPatternProps(
                agent_runtime_name='ResponseGenerator',
                source_code_path='assets/agent_code/response_generator',
                agent_runtime_environment_variables={
                    'MULTI_AGENT_MODEL_ID': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
                    'RESPONSE_GENERATOR_MODEL_ID': 'us.anthropic.claude-opus-4-6-v1'
                }
            )
        )

        self.document_classifier_app = AgentCoreAppPattern(
            self, 'DocumentClassifierApp',
            AgentCoreAppPatternProps(
                agent_runtime_name='DocumentClassifier',
                source_code_path='assets/agent_code/document_classifier',
                agent_runtime_environment_variables={
                    'MODEL_ID': 'us.anthropic.claude-3-5-sonnet-20240620-v1:0',
                    'RAW_FILES_BUCKET': core_stack.raw_files_bucket.bucket_name,
                    'STAGING_BUCKET': core_stack.staging_bucket.bucket_name,
                    'HISTORIC_FILES_BUCKET': core_stack.historic_files_bucket.bucket_name,
                    'RUNNING_LOCALLY': '0'
                },
                runtime_invocations_table=self.response_generator_app.runtime_invocations_table,
                runtime_invocations_queue=self.response_generator_app.runtime_invocations_queue,
                runtime_invocations_consumer=self.response_generator_app.runtime_invocations_consumer
            )
        )

        for app in [self.response_generator_app, self.document_classifier_app]:
            core_stack.historic_files_bucket.grant_read_write(app.role)
            core_stack.raw_files_bucket.grant_read_write(app.role)
            core_stack.staging_bucket.grant_read_write(app.role)
            core_stack.clean_files_bucket.grant_read_write(app.role)
            core_stack.output_files_bucket.grant_read_write(app.role)

            app.role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "bedrock:Retrieve"
                    ],
                    resources=["*"]
                )
            )

            NagSuppressions.add_resource_suppressions(
                app,
                apply_to_children=True,
                suppressions=[
                    {
                        "id": 'AwsSolutions-IAM5',
                        "reason": "Wildcard needed to track all KnowledgeBases created dynamically"
                    }
                ],
            )
