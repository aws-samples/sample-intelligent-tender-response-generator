import json

from aws_cdk import (
    RemovalPolicy,
    Stack,
    aws_iam as iam,
    # aws_ec2 as ec2,  # Unused: see the commented-out VPC block below.
    aws_opensearchserverless as aoss,
    CfnOutput,
    aws_lambda as _lambda,
    custom_resources as cr,
    aws_s3 as s3,
    Duration
)
from cdk_nag import NagSuppressions
from constructs import Construct

class CoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open('project_config.json', 'r') as file:
            variables = json.load(file)

        # NOTE: This sample is fully serverless — Lambda functions, Bedrock
        # AgentCore runtimes (PUBLIC network mode) and OpenSearch Serverless all
        # run outside a customer VPC and reach AWS services over public/managed
        # endpoints. The VPC below is therefore unused: nothing is placed in it
        # and it is not exported to any other stack. It is left commented out to
        # avoid provisioning an idle VPC + NAT gateway (a recurring cost) for no
        # functional benefit. If you later add VPC-bound resources, re-enable
        # this block and pass `vpc` to those constructs.
        #
        # cidr_range = variables["vpc"]["cidr_range"]
        # cidr_mask = variables["vpc"]["cidr_mask"]
        #
        # public_subnet = ec2.SubnetConfiguration(
        #     name="PublicSubnet",
        #     subnet_type=ec2.SubnetType.PUBLIC,
        #     cidr_mask=cidr_mask,
        # )
        #
        # private_subnet = ec2.SubnetConfiguration(
        #     name="PrivateSubnet",
        #     subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        #     cidr_mask=cidr_mask,
        # )
        #
        # vpc = ec2.Vpc(
        #     scope=self,
        #     id="VPC",
        #     ip_addresses=ec2.IpAddresses.cidr(cidr_range),
        #     subnet_configuration=[public_subnet, private_subnet],
        #     flow_logs={
        #         "cloudwatch": ec2.FlowLogOptions(
        #             destination=ec2.FlowLogDestination.to_cloud_watch_logs()
        #         )
        #     },
        # )

        access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            auto_delete_objects=True,
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
        )

        self.historic_files_bucket = s3.Bucket(
            self, "HistoricFilesBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True
        )

        self.raw_files_bucket = s3.Bucket(
            self, "RawFilesBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.POST, s3.HttpMethods.PUT],
                    allowed_origins=["*"],
                    allowed_headers = ["*"],
                    max_age = 3000
                )
            ],
        )

        self.clean_files_bucket = s3.Bucket(
            self, "CleanFilesBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.POST, s3.HttpMethods.PUT],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000
                )
            ],
        )

        self.staging_bucket = s3.Bucket(
            self,"StagingBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
        )

        self.output_files_bucket = s3.Bucket(
            self, "OutputBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000
                )
            ],
        )

        self.multimodal_bucket = s3.Bucket(
            self,"MultimodalStorageBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True
        )

        # Create Studio Role with Bedrock access
        self.kb_role = iam.Role(
            self,
            "KBRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonBedrockFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonOpenSearchServiceFullAccess"
                ),
            ],
        )

        self.kb_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["aoss:APIAccessAll"],
            resources=["*"],
        ))

        self.multimodal_bucket.grant_read_write(self.kb_role)

        self.aoss_encryption_policy = aoss.CfnSecurityPolicy(
            self, "AossEncryptionPolicy",
            name="kb-encryption-policy",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": ["collection/*"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )

        self.aoss_network_policy = aoss.CfnSecurityPolicy(
            self, "AossNetworkPolicy",
            name="kb-network-policy",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/*"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )

        oss_index_waiter_fn = _lambda.Function(
            self, 'IndexWaiterFunc',
            function_name='indexWaiter',
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_wait_for_oss_index_creation'),
            timeout=Duration.minutes(10),
        )

        oss_index_waiter_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "aoss:APIAccessAll",
                "aoss:GetIndex"
            ],
            resources=["*"],
        ))

        oss_index_waiter_provider = cr.Provider(self, "AossIndexWaiterProvider", on_event_handler=oss_index_waiter_fn)

        aoss.CfnAccessPolicy(
            self, "OSSDataAccessPolicy",
            name=f"access-policy-{self.stack_name.lower()}",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [
                                    f"collection/*"
                                ],
                                "Permission": [
                                    "aoss:DescribeCollectionItems",
                                    "aoss:CreateCollectionItems",
                                    "aoss:UpdateCollectionItems"
                                ]
                            },
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/*/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                            }
                        ],
                        "Principal": [
                            self.kb_role.role_arn,
                            oss_index_waiter_fn.role.role_arn,
                            f"arn:aws:iam::{self.account}:role/cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}"
                        ],
                    }
                ]
            ),
        )

        # CDK Nag Suppressions for StudioRole managed policies
        for mngPolicy in ['AmazonS3FullAccess', 'AmazonBedrockFullAccess', 'AmazonOpenSearchServiceFullAccess']:
            NagSuppressions.add_resource_suppressions(
                self.kb_role,
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": f"{mngPolicy} managed policy is required by Bedrock Knowledge Bases to access resources.",
                        "appliesTo": [
                            f"Policy::arn:<AWS::Partition>:iam::aws:policy/{mngPolicy}"
                        ],
                    }
                ],
            )

        NagSuppressions.add_resource_suppressions(
            construct=self.kb_role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "The role needs read/write permission to the multimodal S3 bucket."
                }
            ],
            apply_to_children=True,
        )

        for sup_id in ['AwsSolutions-IAM5', 'AwsSolutions-IAM4']:
            NagSuppressions.add_resource_suppressions(
                construct=oss_index_waiter_fn,
                suppressions=[
                    {
                        "id": sup_id,
                        "reason": "Needs to describe all index created dynamically."
                    }
                ],
                apply_to_children=True,
            )

        for sup_id in ['AwsSolutions-IAM5', 'AwsSolutions-IAM4', 'AwsSolutions-L1']:
            NagSuppressions.add_resource_suppressions(
                construct=oss_index_waiter_provider,
                suppressions=[
                    {
                        "id": sup_id,
                        "reason": "Policy is required."
                    }
                ],
                apply_to_children=True,
            )

        CfnOutput(
            self, "AossIndexWaiterServiceTokenExport",
            value=oss_index_waiter_provider.service_token,
            export_name="AossIndexWaiterProviderServiceToken",
        )

        CfnOutput(
            self, "KbRoleARNExport",
            value=self.kb_role.role_arn,
            export_name="KbRoleARN",
        )

        CfnOutput(
            self, "InputBucketARNExport",
            value=self.clean_files_bucket.bucket_arn,
            export_name="InputBucketARN",
        )

        CfnOutput(
            self, "MultimodalBucketNameExport",
            value=self.multimodal_bucket.bucket_name,
            export_name="MultimodalBucketName",
        )
