import os

from aws_cdk import (
    aws_apigateway as apigateway,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_amplify_alpha as amplify,
    aws_lambda as _lambda,
    aws_iam as iam,
    custom_resources as cr,
    RemovalPolicy,
    Stack,
    Annotations
)
from constructs import Construct
from .props import *
from cdk_nag import NagSuppressions


class WebAppPattern(Construct):
    __ARCH = _lambda.Architecture.ARM_64
    __ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

    def __init__(self, scope: Construct, construct_id: str, props: WebAppPatternProps) -> None:
        super().__init__(scope, construct_id)

        self.app = self.__create_application(props)

        # Create security resources
        user_pool, user_pool_domain = self.__create_user_pool(props)
        user_pool_client = self.__create_user_pool_client(props, user_pool)
        cognito_authority = f'https://cognito-idp.{Stack.of(self).region}.amazonaws.com/{user_pool.user_pool_id}'
        cognito_domain = f"https://{user_pool_domain.domain_name}.auth.{Stack.of(self).region}.amazoncognito.com"
        self.user_pool_id = user_pool.user_pool_id
        self.user_pool_client_id = user_pool_client.user_pool_client_id

        # Create networking resources
        self.api_authorizer = self.__create_authorizer(user_pool)
        self.api = self.__create_api(props, self.app.app_id)
        cfn_key = self.__create_api_key(props)
        api_key_value = self.__resolve_api_key_value(cfn_key)
        api_invoke_url = f'https://{self.api.rest_api_id}.execute-api.{Stack.of(self).region}.amazonaws.com/dev'

        if props.deploy_test_endpoint:
            self.__create_test_integration(props, self.api, self.api_authorizer)

        # Define Amplify application environment variables
        self.app.add_environment(f'{props.framework_variable_prefix}_USER_POOL_CLIENT_ID', self.user_pool_client_id)
        self.app.add_environment(f'{props.framework_variable_prefix}_COGNITO_AUTHORITY', cognito_authority)
        self.app.add_environment(f'{props.framework_variable_prefix}_COGNITO_DOMAIN', cognito_domain)
        self.app.add_environment(f'{props.framework_variable_prefix}_API_URL', api_invoke_url)
        # The API key value is resolved at deploy time and injected so the
        # front-end can send the required 'x-api-key' header. Without this the
        # api-key-protected endpoints (e.g. enum categories) return 403 and the
        # UI renders empty dropdowns.
        self.app.add_environment(f'{props.framework_variable_prefix}_API_KEY', api_key_value)

        Annotations.of(self).add_warning(
            "Reminder: You must manually add the Amplify app domain to the list of Cognito App Client callback and sign-out URLs."
        )

        NagSuppressions.add_resource_suppressions(
            self.api,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using AWS-managed policy for API Gateway CW logging in this environment.",
                }
            ],
            apply_to_children=True
        )


    # ------------------ FRONTEND ------------------ #
    def __create_application(self, props):
        app = amplify.App(
            self, 'AmplifyApp',
            source_code_provider=props.code_provider,
            app_name=props.app_name,
            environment_variables=props.env_vars
        )

        app.add_branch(
            'AmplifyAppBranch',
            auto_build=True,
            branch_name=props.branch_name,
            basic_auth=props.branch_auth
        )

        return app

    # ------------------ SECURITY ------------------ #
    def __create_user_pool(self, props):
        user_pool = cognito.UserPool(
            self, 'UserPool',
            feature_plan=cognito.FeaturePlan.PLUS,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=False, email=True),
            user_pool_name=props.user_pool_name,
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=False
                )
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
        )

        domain = cognito.UserPoolDomain(
            self, 'UserPoolDomain',
            user_pool=user_pool,
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=props.user_pool_domain_prefix),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN
        )

        return user_pool, domain

    def __create_user_pool_client(self, props, user_pool):
        urls = [
            "http://localhost:3000",
            "https://localhost:3000"
        ]

        client = cognito.UserPoolClient(
            self, 'UserPoolClient',
            user_pool=user_pool,
            user_pool_client_name=props.user_pool_client_name,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True
                ),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=urls,
                logout_urls=[f'{url}/login' for url in urls]
            )
        )

        cognito.CfnManagedLoginBranding(
            self, 'LoginBranding',
            user_pool_id=user_pool.user_pool_id,
            client_id=client.user_pool_client_id,
            use_cognito_provided_values=True
        )

        return client

    # ----------------- NETWORKING ----------------- #
    def __create_test_integration(self, props, api, authorizer):
        func = _lambda.Function(
            self, 'TestFunc',
            handler='index.handler',
            architecture=self.__ARCH,
            runtime=props.python_runtime,
            function_name=f'{api.rest_api_name}TestFunc',
            code=_lambda.Code.from_asset(f'{self.__ASSETS_PATH}/lambda/func_test'),
            log_group=logs.LogGroup(
                self, 'TestFuncLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        resource = api.root.add_resource('test')
        resource.add_method(
            'GET',
            apigateway.LambdaIntegration(func),
            authorizer=authorizer,
            api_key_required=True
        )

        NagSuppressions.add_resource_suppressions(
            func.role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "This is a dummy function deployed to test the User pool authorizer.",
                }
            ],
        )

    def __create_authorizer(self, user_pool):
        return apigateway.CognitoUserPoolsAuthorizer(
            self, 'CognitoAuthorizer',
            authorizer_name='CognitoAuthorizer',
            cognito_user_pools=[user_pool]
        )

    def __create_api_key(self, props):
        # Usage plan
        plan = apigateway.CfnUsagePlan(
            self, "UsagePlan",
            throttle=props.api_key_throttle
        )

        plan.api_stages = [
            apigateway.CfnUsagePlan.ApiStageProperty(
                api_id=self.api.rest_api_id,
                stage=self.api.deployment_stage.stage_name
            )
        ]

        # Create an API Key
        cfn_key = apigateway.CfnApiKey(
            self, "ApiKey",
            enabled=True,
            name=props.api_key_name
        )

        # Attach key to usage plan
        apigateway.CfnUsagePlanKey(
            self, "PlanKey",
            key_id=cfn_key.ref,
            key_type="API_KEY",
            usage_plan_id=plan.ref
        )

        return cfn_key

    def __resolve_api_key_value(self, cfn_key):
        # The generated API key value is not available as a CloudFormation
        # attribute, so resolve it at deploy time via an AwsCustomResource that
        # calls apigateway:GetApiKey with includeValue=true. The resolved value
        # is then injected into the front-end as an environment variable.
        get_key = cr.AwsCustomResource(
            self, "GetApiKeyValue",
            on_create=cr.AwsSdkCall(
                service="APIGateway",
                action="getApiKey",
                parameters={
                    "apiKey": cfn_key.ref,
                    "includeValue": True,
                },
                physical_resource_id=cr.PhysicalResourceId.of(cfn_key.ref),
            ),
            on_update=cr.AwsSdkCall(
                service="APIGateway",
                action="getApiKey",
                parameters={
                    "apiKey": cfn_key.ref,
                    "includeValue": True,
                },
                physical_resource_id=cr.PhysicalResourceId.of(cfn_key.ref),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["apigateway:GET"],
                    resources=[
                        Stack.of(self).format_arn(
                            service="apigateway",
                            account="",
                            resource="/apikeys/*",
                        )
                    ],
                )
            ]),
        )

        get_key.node.add_dependency(cfn_key)

        NagSuppressions.add_resource_suppressions(
            get_key,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "The custom resource must read the generated API key value; "
                              "apigateway:GET is scoped to the /apikeys/* resource path.",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Lambda runtime for this CDK-managed custom resource is controlled by the framework.",
                },
            ],
            apply_to_children=True,
        )

        return get_key.get_response_field("value")

    def __create_api(self, props, app_id):
        props.api_allowed_origins.extend([
            f'https://{props.branch_name}.{app_id}.amplifyapp.com'
        ])

        access_logs = logs.LogGroup(
            self, "ApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        api = apigateway.RestApi(
            self, 'RestApi',
            rest_api_name=props.api_name,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=props.api_allowed_headers,
                allow_credentials=True,
            ),
            deploy=True,
            retain_deployments=False,
            deploy_options=apigateway.StageOptions(
                stage_name='dev',
                variables={
                    'env': 'dev'
                },
                logging_level=apigateway.MethodLoggingLevel.ERROR,
                access_log_destination=apigateway.LogGroupLogDestination(access_logs),
            ),
            cloud_watch_role=True
        )

        apigateway.RequestValidator(
            self, "BasicRequestValidator",
            rest_api=api,
            validate_request_body=True,
            validate_request_parameters=True
        )

        return api
