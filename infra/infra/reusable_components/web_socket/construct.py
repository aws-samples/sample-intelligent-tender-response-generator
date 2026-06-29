import os

from aws_cdk import (
    aws_dynamodb as ddb,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_apigatewayv2_authorizers as apigwv2_authorizers,
    RemovalPolicy,
    Duration,
    Stack,
    Annotations,
    aws_logs as logs,
)

from constructs import Construct
from .props import WebSocketPatternProps
from cdk_nag import NagSuppressions
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion


class WebSocketPattern(Construct):
    __ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets/lambda')
    __ARCH = _lambda.Architecture.ARM_64

    def __init__(self, scope: Construct, construct_id: str, props: WebSocketPatternProps):
        super().__init__(scope, construct_id)

        self.connections_table = self.__create_connections_table(props)
        self.__layer = self.__create_layer(props)
        on_connect, on_disconnect, on_default = self.__create_lifecycle_functions(props, self.connections_table)
        self.authorizer, authorizer_fn = self.__create_authorizer(props)
        self.api, stage = self.__create_api(props, on_connect, on_disconnect, on_default, self.authorizer)
        self.wss_url = f"wss://{self.api.api_id}.execute-api.{Stack.of(self).region}.amazonaws.com/{props.stage_name}"

        Annotations.of(self).add_warning(
            "Info: When connecting to the web socket, pass the user token as a query string parameter using `token` as parameter name."
        )

        for fn in (on_connect, on_disconnect, on_default):
            self.api.grant_manage_connections(fn)

            NagSuppressions.add_resource_suppressions(
                fn,
                suppressions=[
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "Using AWS managed policy for basic CloudWatch Logs; app-specific access is granted via inline policies.",
                    },
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "execute-api:ManageConnections requires wildcard on connection IDs."
                    }
                ],
                apply_to_children=True,
            )

        NagSuppressions.add_resource_suppressions(
            authorizer_fn,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using AWS managed policy for basic CloudWatch Logs; app-specific access is granted via inline policies.",
                }
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            stage,
            suppressions=[
                {
                    "id": "AwsSolutions-APIG1",
                    "reason": "Can't enable logging using the alpha package.",
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self.api,
            apply_to_children=True,
            suppressions=[
                {
                    "id": "AwsSolutions-APIG4",
                    "reason": "Can't implement authorization in the disconnect and default routes."
                }
            ]
        )

    def __create_connections_table(self, props):
        table = ddb.Table(
            self,"ConnectionsTable",
            table_name=props.connections_table_name,
            partition_key=ddb.Attribute(name="connectionId", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
            time_to_live_attribute=props.ttl_attr_name
        )

        table.add_global_secondary_index(
            index_name="byUserId",
            partition_key=ddb.Attribute(name="userId", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.ALL,
        )

        return table

    def __create_lifecycle_functions(self, props, table):
        common_env = {
            "TABLE_NAME": table.table_name,
            'TTL_ATTR': props.ttl_attr_name,
            'TTL_HOURS': props.connections_ttl_hours,
        }

        on_connect_fn = _lambda.Function(
            self,"OnConnectFn",
            runtime=props.python_runtime,
            architecture=self.__ARCH,
            handler="index.handler",
            function_name=f'{props.api_name}OnConnect',
            code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_on_connect"),
            timeout=Duration.seconds(10),
            environment=common_env,
            layers=[self.__layer],
            log_group=logs.LogGroup(
                self, 'OnConnectFnLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        on_disconnect_fn = _lambda.Function(
            self,"OnDisconnectFn",
            runtime=props.python_runtime,
            architecture=self.__ARCH,
            handler="index.handler",
            function_name=f'{props.api_name}OnDisconnect',
            code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_on_disconnect"),
            timeout=Duration.seconds(10),
            environment=common_env,
            layers=[self.__layer],
            log_group=logs.LogGroup(
                self, 'OnDisconnectFnLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        on_default_fn = props.onDefaultHandler if props.onDefaultHandler is not None else (
            _lambda.Function(
                self,"OnDefaultFn",
                runtime=props.python_runtime,
                architecture=self.__ARCH,
                handler="index.handler",
                function_name=f'{props.api_name}OnDefault',
                code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_on_default"),
                timeout=Duration.seconds(10),
                environment=common_env,
                layers=[self.__layer],
                log_group=logs.LogGroup(
                    self, 'OnDefaultFnLogGroup',
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            )
        )

        table.grant_write_data(on_connect_fn)
        table.grant_read_write_data(on_disconnect_fn)
        table.grant_read_data(on_default_fn)

        return on_connect_fn, on_disconnect_fn, on_default_fn

    def __create_authorizer(self, props):
        authorizer_fn = _lambda.Function(
            self,"JwtAuthorizerFn",
            architecture=self.__ARCH,
            runtime=props.python_runtime,
            handler="index.handler",
            function_name=f'{props.api_name}Authorizer',
            code=_lambda.Code.from_asset(f"{self.__ASSETS_PATH}/func_authorizer"),
            timeout=Duration.seconds(10),
            environment={
                "USER_POOL_ID": props.user_pool_id,
                "USER_POOL_CLIENT_ID": props.user_pool_client_id
            },
            layers=[self.__layer],
            log_group=logs.LogGroup(
                self, 'JwtAuthorizerFnFnLogGroup',
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

        authorizer = apigwv2_authorizers.WebSocketLambdaAuthorizer(
            "CognitoJwtAuthorizer",
            handler=authorizer_fn,
            identity_source=['route.request.querystring.token'],
        )

        return authorizer, authorizer_fn

    def __create_layer(self, props):
        return PythonLayerVersion(
            self, 'Layer',
            layer_version_name=f'{props.api_name}Deps',
            entry=f"{self.__ASSETS_PATH}/layer",
            compatible_runtimes=[props.python_runtime],
            compatible_architectures=[self.__ARCH],
            removal_policy=RemovalPolicy.DESTROY
        )

    def __create_api(self, props, on_connect, on_disconnect, on_default, authorizer):
        api = apigwv2.WebSocketApi(
            self, props.api_name,
            api_name=props.api_name,
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    on_connect
                ),
                authorizer=authorizer,
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration",
                    on_disconnect
                )
            ),
            default_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigwv2_integrations.WebSocketLambdaIntegration(
                    "DefaultIntegration",
                    on_default
                )
            )
        )

        stage = apigwv2.WebSocketStage(
            self,"Stage",
            web_socket_api=api,
            stage_name=props.stage_name,
            auto_deploy=True
        )

        return api, stage
