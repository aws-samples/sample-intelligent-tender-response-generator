import os
import zipfile

from aws_cdk import (
    CfnOutput,
    Stack,
    aws_codecommit as codecommit,
)
from constructs import Construct
from cdk_nag import NagSuppressions
from .reusable_components import *


class FrontendStack(Stack):
    @staticmethod
    def zip_web_app_code(source_dir: str, output_path: str, excludes: list = None, exclude_files: list = None):
        """Create a zip of the front-end source to seed the CodeCommit repository.

        Directories listed in ``excludes`` and files listed in ``exclude_files`` are
        skipped so build artifacts and local-only files are not published.
        """
        excludes = excludes or []
        exclude_files = exclude_files or []

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in excludes]

                for file in files:
                    if file not in exclude_files:
                        abs_path = os.path.join(root, file)
                        arc_path = os.path.relpath(abs_path, source_dir)

                        zf.write(abs_path, arc_path)

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The front-end source lives as a sibling of the infra CDK project
        # (auto-tender/front-end). Zip it at synth time and seed a CodeCommit
        # repository from it so `cdk deploy --all` is self-contained.
        web_app_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'front-end')
        )
        web_app_zip = f'{web_app_path}.zip'

        self.zip_web_app_code(
            web_app_path, web_app_zip,
            excludes=['.idea', 'node_modules', '.git', 'build'],
            exclude_files=['.DS_Store', '.env'],
        )

        repo = codecommit.Repository(
            self, 'CodeCommitRepository',
            repository_name='tender-response-generator-frontend',
            code=codecommit.Code.from_zip_file(
                file_path=web_app_zip,
                branch='main',
            ),
        )

        self.repo = repo

        self.web_app = WebAppPattern(
            self, 'WebAppPattern',
            WebAppPatternProps(
                deploy_test_endpoint=False,
                user_pool_name='TenderResponseGenerator',
                user_pool_domain_prefix='tender-response-generator',
                user_pool_client_name='TenderResponseGenerator',
                app_name='TenderResponseGenerator',
                api_allowed_origins=['localhost:3000'],
                code_provider=CodeCommitSourceCodeProvider(repository=repo),
            )
        )

        self.web_socket = WebSocketPattern(
            self, 'WebSocketPattern',
            WebSocketPatternProps(
                user_pool_id=self.web_app.user_pool_id,
                user_pool_client_id=self.web_app.user_pool_client_id
            )
        )

        self.web_app.app.add_environment('REACT_APP_WSS_URL', self.web_socket.wss_url)

        WafPattern(
            self, 'WafPattern',
            WafPatternProps(
                resource_mappings={
                    self.web_app.app.arn: WafPatternProps.AclProps(
                        acl_name='WebAppAcl',
                        scope='CLOUDFRONT',
                        acl_rules=[
                            'AWSManagedRulesCommonRuleSet',
                            'AWSManagedRulesKnownBadInputsRuleSet',
                            'AWSManagedRulesSQLiRuleSet',
                        ]
                    ),
                    self.web_app.api.deployment_stage.stage_arn: WafPatternProps.AclProps(
                        acl_name='RestApiAcl',
                        scope='REGIONAL',
                        acl_rules=[
                            'AWSManagedRulesCommonRuleSet',
                            'AWSManagedRulesKnownBadInputsRuleSet',
                            'AWSManagedRulesAmazonIpReputationList',
                        ]
                    )
                }
            )
        )

        # Convenience outputs for locating the deployed resources after deploy.
        CfnOutput(
            self, 'UserPoolId',
            value=self.web_app.user_pool_id,
            description='Cognito User Pool id. Create a user here to sign in to the web app.',
        )

        CfnOutput(
            self, 'AmplifyAppDomain',
            value=f'https://{self.web_app.app.default_domain}',
            description='Default Amplify-hosted domain for the front-end application.',
        )

        CfnOutput(
            self, 'FrontendRepositoryCloneUrl',
            value=repo.repository_clone_url_http,
            description='HTTPS clone URL of the CodeCommit repository that hosts the front-end source.',
        )

        # The AwsCustomResource that resolves the API key value provisions a
        # CDK-managed singleton Lambda whose service role uses the AWS-managed
        # AWSLambdaBasicExecutionRole policy. This Lambda is framework-owned and
        # not customer-configurable, so the managed-policy finding is suppressed.
        NagSuppressions.add_stack_suppressions(
            self,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK-managed AwsCustomResource provider Lambda uses the AWS-managed "
                              "AWSLambdaBasicExecutionRole; this provider role is framework-owned.",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Lambda runtime for the CDK-managed AwsCustomResource provider is "
                              "controlled by the framework, not by this stack.",
                },
            ],
        )
