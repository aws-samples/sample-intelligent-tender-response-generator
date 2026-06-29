import os

from aws_cdk import (
    aws_ecr as ecr,
    RemovalPolicy,
    aws_s3_assets as s3_assets,
    aws_iam as iam,
    aws_codebuild as codebuild,
    aws_lambda as _lambda,
    aws_bedrockagentcore as bedrockagentcore,
    aws_dynamodb as ddb,
    aws_sqs as sqs,
    Stack,
    Duration,
    CustomResource,
    aws_logs as logs,
    aws_kms as kms
)
from constructs import Construct
from cdk_nag import NagSuppressions
from .props import AgentCoreAppPatternProps
from .agentcore_role import AgentCoreRole


class AgentCoreAppPattern(Construct):
    __ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
    __ARCH = _lambda.Architecture.ARM_64

    def __init__(self, scope: Construct, id: str, props: AgentCoreAppPatternProps):
        super().__init__(scope, id)

        self.runtime_invocations_table = props.runtime_invocations_table or self.__create_runtime_invocations_table(props)
        self.runtime_invocations_queue = props.runtime_invocations_queue or self.__create_runtime_invocations_queue(props)
        self.runtime_invocations_consumer = (props.runtime_invocations_consumer or
                                             self.__create_runtime_invocations_consumer(props, self.runtime_invocations_table))

        self.__link_queue_table_and_consumer(
            self.runtime_invocations_queue, self.runtime_invocations_table, self.runtime_invocations_consumer
        )

        self.role = AgentCoreRole(self, "AgentCoreRole")
        self.runtime_invocations_queue.grant_send_messages(self.role)

        ecr_repository = self.__create_ecr_repository(props)
        source_asset = s3_assets.Asset(self, "SourceAsset", path=props.source_code_path)
        codebuild_role = self.__create_codebuild_role(props, ecr_repository, source_asset)
        codebuild_project = self.__create_codebuild_project(props, codebuild_role, source_asset, ecr_repository)
        build_func, build_trigger = self.__create_build_trigger(props, codebuild_project, source_asset)

        self.agentcore_runtime = self.__create_agentcore_runtime(props, ecr_repository, self.role)
        self.agentcore_runtime.node.add_dependency(build_trigger)

        for func in [build_func, self.runtime_invocations_consumer]:
            NagSuppressions.add_resource_suppressions(
                func,
                suppressions=[
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "Using AWS managed policy for basic CloudWatch Logs; app-specific access is granted via inline policies.",
                    }
                ],
                apply_to_children=True,
            )

    def __create_ecr_repository(self, props: AgentCoreAppPatternProps):
        return ecr.Repository(
            self, "ECRRepository",
            repository_name=f'{props.agent_runtime_name}-repository'.lower(),
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            image_scan_on_push=True,
        )

    def __create_codebuild_role(self, props: AgentCoreAppPatternProps, ecr_repository: ecr.Repository,
                                source_asset: s3_assets.Asset):
        return iam.Role(
            self,"CodeBuildRole",
            role_name=f"{props.agent_runtime_name}-codebuild-role",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies={
                "CodeBuildPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="CloudWatchLogs",
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/codebuild/*"
                            ],
                        ),
                        iam.PolicyStatement(
                            sid="ECRAccess",
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "ecr:GetAuthorizationToken",
                                "ecr:PutImage",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                            ],
                            resources=[ecr_repository.repository_arn, "*"],
                        ),
                        iam.PolicyStatement(
                            sid="S3SourceAccess",
                            effect=iam.Effect.ALLOW,
                            actions=["s3:GetObject"],
                            resources=[f"{source_asset.bucket.bucket_arn}/*"],
                        ),
                    ]
                )
            },
        )

    def __create_codebuild_project(self, props: AgentCoreAppPatternProps, codebuild_role: iam.Role,
                                   source_asset: s3_assets.Asset, ecr_repository: ecr.Repository):
        key = kms.Key(
            self, "CodeBuildEncryptionKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )

        return codebuild.Project(
            self,"AgentImageBuildProject",
            project_name=f"{props.agent_runtime_name}-code-build-project",
            description=f"Build agent Docker image for {props.agent_runtime_name}",
            role=codebuild_role,
            timeout=Duration.minutes(60),
            environment=props.codebuild_environment,
            source=codebuild.Source.s3(
                bucket=source_asset.bucket, path=source_asset.s3_object_key
            ),
            build_spec=codebuild.BuildSpec.from_asset(f'{self.__ASSETS_PATH}/buildspec.json'),
            encryption_key=key,
            environment_variables={
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(
                    value=Stack.of(self).region
                ),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=Stack.of(self).account),
                "IMAGE_REPO_NAME": codebuild.BuildEnvironmentVariable(
                    value=ecr_repository.repository_name
                ),
                "IMAGE_TAG": codebuild.BuildEnvironmentVariable(
                    value=props.image_tag
                ),
                "STACK_NAME": codebuild.BuildEnvironmentVariable(
                    value=Stack.of(self).stack_name
                ),
            },
        )

    def __create_build_trigger(self, props, codebuild_project: codebuild.Project, source_asset: s3_assets.Asset):
        func = _lambda.Function(
            self,"BuildTriggerFunction",
            function_name=f"{props.agent_runtime_name}-build-trigger",
            runtime=props.python_runtime,
            handler="index.handler",
            timeout=Duration.minutes(15),
            code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_project_builder"),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                    resources=[codebuild_project.project_arn],
                )
            ],
            log_group=logs.LogGroup(
                self, 'BuildTriggerFunctionLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            )
        )

        trigger = CustomResource(
            self,"BuildTriggerFunctionCustomResource",
            service_token=func.function_arn,
            properties={
                "ProjectName": codebuild_project.project_name,
                "SourceHash": source_asset.asset_hash
            },
        )

        trigger.node.add_dependency(source_asset)
        trigger.node.add_dependency(codebuild_project)

        return func, trigger

    def __create_agentcore_runtime(self, props: AgentCoreAppPatternProps, ecr_repository: ecr.Repository, role: iam.Role):
        props.agent_runtime_environment_variables.update({
            "AWS_DEFAULT_REGION": Stack.of(self).region,
            'RUNTIME_INVOCATIONS_QUEUE_URL': self.runtime_invocations_queue.queue_url
        })

        return bedrockagentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name=props.agent_runtime_name,
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{ecr_repository.repository_uri}:{props.image_tag}"
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode=props.agent_runtime_network_mode,
            ),
            protocol_configuration="HTTP",
            role_arn=role.role_arn,
            description=f"Agent runtime for {props.agent_runtime_name}",
            environment_variables=props.agent_runtime_environment_variables,
        )

    def __create_runtime_invocations_table(self, props):
        return ddb.Table(
            self, 'RuntimeInvocationsTable',
            table_name=props.runtime_invocations_table_name,
            partition_key=ddb.Attribute(type=ddb.AttributeType.NUMBER, name=props.partition_key_attr_name),
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute=props.ttl_attr_name
        )

    def __create_runtime_invocations_queue(self, props):
        dlq = sqs.Queue(
            self,"RuntimeInvocationsDLQ",
            queue_name=f'{props.runtime_invocations_queue_name}-DLQ',
            retention_period=Duration.days(14),
            enforce_ssl=True,
        )

        return sqs.Queue(
            self,"RuntimeInvocationsQueue",
            queue_name=props.runtime_invocations_queue_name,
            visibility_timeout=Duration.seconds(60),
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=dlq,
            ),
        )

    def __create_runtime_invocations_consumer(self, props, table):
        return _lambda.Function(
            self, 'RuntimeInvocationsQueueConsumer',
            function_name=props.runtime_invocations_consumer_name,
            handler="index.handler",
            runtime=props.python_runtime,
            architecture=self.__ARCH,
            timeout=Duration.minutes(1),
            code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_consume_runtime_invocations_queue"),
            environment={
                'TABLE_RUNTIME_INVOCATIONS': table.table_name,
                'TTL_DAYS': props.runtime_invocations_ttl_days,
                'TTL_ATTR': props.ttl_attr_name
            },
            log_group=logs.LogGroup(
                self, 'RuntimeInvocationsQueueConsumerLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

    @staticmethod
    def __link_queue_table_and_consumer(queue, table, consumer):
        mapping_id = f"{queue.node.addr}EventSource"
        mapping = consumer.node.try_find_child(mapping_id)

        if mapping is None:
            consumer.add_event_source_mapping(
                mapping_id,
                event_source_arn=queue.queue_arn,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                enabled=True,
            )

        table.grant_write_data(consumer)
        queue.grant_consume_messages(consumer)

    def grant_invoke(self, resource):
        resource.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=['bedrock-agentcore:InvokeAgentRuntime'],
                resources=[
                    f'{self.agentcore_runtime.attr_agent_runtime_arn}/runtime-endpoint/DEFAULT',
                    self.agentcore_runtime.attr_agent_runtime_arn
                ],
            )
        )
