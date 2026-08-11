from aws_cdk import (
    aws_dynamodb as ddb,
    aws_lambda as _lambda,
    aws_lambda_python_alpha as _lambda_python,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_lambda_event_sources as event_sources,
    aws_events as events,
    aws_events_targets as targets,
    Stack,
    RemovalPolicy,
    Duration
)
from constructs import Construct
from cdk_nag import NagSuppressions


class InfraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, core_stack, agentcore_stack, frontend_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        analysis_table = ddb.Table(
            self, 'AnalysisTable',
            table_name='AnalysisTable',
            partition_key=ddb.Attribute(type=ddb.AttributeType.STRING, name="Id"),
            removal_policy=RemovalPolicy.DESTROY,
            stream=ddb.StreamViewType.NEW_AND_OLD_IMAGES
        )

        funcs, layer = self.__create_lambda_resources(
            analysis_table,
            core_stack.historic_files_bucket,
            core_stack.raw_files_bucket,
            core_stack.staging_bucket,
            core_stack.clean_files_bucket,
            core_stack.output_files_bucket,
            agentcore_stack.response_generator_app.agentcore_runtime.attr_agent_runtime_arn,
            agentcore_stack.document_classifier_app.agentcore_runtime.attr_agent_runtime_arn,
            agentcore_stack.document_classifier_app.runtime_invocations_table,
        )

        self.__create_func_consume_ddb_stream(analysis_table, 'WebSocketConnections', layer)
        self.__create_api_gateway_resources(funcs, frontend_stack.web_app.api, frontend_stack.web_app.api_authorizer)
        self.orchestrator_func = funcs['Orchestrator']
        self.__create_capture_workflow_errors_rule(funcs['CaptureWorkflowErrors'])

    def __create_lambda_resources(self, analysis_table, historic_files_bucket, raw_files_bucket, staging_bucket, clean_files_bucket, output_files_bucket,
                                  response_generator_runtime_arn, document_classifier_runtime_arn, table_runtime_invocations):
        runtime = _lambda.Runtime.PYTHON_3_14
        arch = _lambda.Architecture.ARM_64

        layer = _lambda.LayerVersion(
            self, 'LayerVersion',
            layer_version_name='SystemLayer',
            compatible_runtimes=[runtime],
            compatible_architectures=[arch],
            code=_lambda.Code.from_asset('assets/lambda/layer')
        )

        chunk_files_func = _lambda_python.PythonFunction(
            self, 'ChunkFilesFunc',
            runtime=runtime,
            architecture=arch,
            index='index.py',
            handler='handler',
            entry='assets/lambda/func_chunk_pdf_files',
            layers=[layer],
            timeout=Duration.minutes(15),
            function_name='chunkFiles',
            environment={
                'SRC_BUCKET': staging_bucket.bucket_name,
                'DST_BUCKET': clean_files_bucket.bucket_name,
                'MAX_PAGES': '100',
                'PAGE_OVERLAP': '0.1'
            },
            memory_size=2048,
        )

        clean_files_bucket.grant_write(chunk_files_func)
        staging_bucket.grant_read(chunk_files_func)

        select_reference_response_func = _lambda.Function(
            self, 'SelectReferenceResponseFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_select_reference_response'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='selectReferenceResponse',
            environment={
                'BUCKET': historic_files_bucket.bucket_name,
                'CLEAN_FILES_BUCKET': clean_files_bucket.bucket_name,
            }
        )

        historic_files_bucket.grant_read(select_reference_response_func)
        clean_files_bucket.grant_write(select_reference_response_func)

        orchestrator_func = _lambda.Function(
            self, 'OrchestratorFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_analysis_workflow_orchestrator'),
            layers=[layer],
            timeout=Duration.minutes(5),
            durable_config=_lambda.DurableConfig(
                execution_timeout=Duration.hours(5),
                retention_period=Duration.days(30)
            ),
            environment={
                'TABLE_ANALYSIS': analysis_table.table_name,
                'TABLE_RUNTIME_INVOCATIONS': table_runtime_invocations.table_name,
                'CF_DEPLOY_ARN': f"arn:aws:iam::{self.account}:role/cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}",
                'DOCUMENT_CLASSIFIER_RUNTIME_ARN': document_classifier_runtime_arn,
                'RESPONSE_GENERATOR_RUNTIME_ARN': response_generator_runtime_arn,
                'FUNC_CHUNK_FILES': chunk_files_func.function_name,
                'FUNC_SELECT_REFERENCE_RESPONSE': select_reference_response_func.function_name,
                'RAW_FILES_BUCKET': raw_files_bucket.bucket_name,
                'STAGING_BUCKET': staging_bucket.bucket_name,
                'CLEAN_FILES_BUCKET': clean_files_bucket.bucket_name,
                'OUTPUT_FILES_BUCKET': output_files_bucket.bucket_name
            }
        )

        table_runtime_invocations.grant_read_data(orchestrator_func)
        analysis_table.grant_read_data(orchestrator_func)
        chunk_files_func.grant_invoke(orchestrator_func)
        select_reference_response_func.grant_invoke(orchestrator_func)
        raw_files_bucket.grant_read(orchestrator_func)

        orchestrator_func.add_to_role_policy(iam.PolicyStatement(
            actions=[
                'lambda:CheckpointDurableExecutions',
                'lambda:GetDurableExecutionState',
                'cloudformation:*',
                'bedrock:StartIngestionJob',
                'bedrock:GetIngestionJob',
                'iam:PassRole',
            ],
            resources=['*']
        ))

        orchestrator_trigger_func = _lambda.Function(
            self, 'OrchestratorTriggerFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_trigger_analysis_workflow'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='analysisWorkflowTrigger',
            environment={
                'RAW_FILES_BUCKET': raw_files_bucket.bucket_name,
                'STAGING_FILES_BUCKET': staging_bucket.bucket_name,
                'CLEAN_FILES_BUCKET': clean_files_bucket.bucket_name,
                'ORCHESTRATOR_FUNC': orchestrator_func.function_name,
                'TABLE_ANALYSIS': analysis_table.table_name
            }
        )

        raw_files_bucket.grant_read_write(orchestrator_trigger_func)
        staging_bucket.grant_read_write(orchestrator_trigger_func)
        clean_files_bucket.grant_read_write(orchestrator_trigger_func)
        orchestrator_func.grant_invoke(orchestrator_trigger_func)

        generate_upload_url_func = _lambda.Function(
            self, 'GenerateUploadUrlFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_generate_upload_url'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='generateUploadUrl',
            environment={
                'DST_BUCKET': raw_files_bucket.bucket_name
            }
        )

        raw_files_bucket.grant_write(generate_upload_url_func)

        generate_download_url_func = _lambda.Function(
            self, 'GenerateDownloadUrlFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_generate_download_url'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='generateDownloadUrl',
            environment={
                'SRC_BUCKET': output_files_bucket.bucket_name
            }
        )

        output_files_bucket.grant_read(generate_download_url_func)

        scan_analysis_func = _lambda.Function(
            self, 'ScanAnalysisFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_scan_analysis'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='scanAnalysis',
            environment={
                'TABLE_ANALYSIS': analysis_table.table_name
            }
        )

        get_analysis_func = _lambda.Function(
            self, 'GetAnalysisFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_get_analysis'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='getAnalysis',
            environment={
                'RAW_FILES_BUCKET': raw_files_bucket.bucket_name,
                'OUTPUT_FILES_BUCKET': output_files_bucket.bucket_name,
                'TABLE_ANALYSIS': analysis_table.table_name
            }
        )

        output_files_bucket.grant_read(get_analysis_func)
        raw_files_bucket.grant_read(get_analysis_func)

        delete_kb_func = _lambda.Function(
            self, 'DeleteKbFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_delete_kb_stack'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='deleteKbStack',
            environment={
                'TABLE_ANALYSIS': analysis_table.table_name
            }
        )

        delete_files_func = _lambda.Function(
            self, 'DeleteFilesFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_delete_analysis_files'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='deleteAnalysisFiles',
            environment={
                'RAW_FILES_BUCKET': raw_files_bucket.bucket_name,
                'STAGING_FILES_BUCKET': staging_bucket.bucket_name,
                'CLEAN_FILES_BUCKET': clean_files_bucket.bucket_name,

            }
        )

        raw_files_bucket.grant_read_write(delete_files_func)
        staging_bucket.grant_read_write(delete_files_func)
        clean_files_bucket.grant_read_write(delete_files_func)

        enum_category_func = _lambda.Function(
            self, 'EnumCategoryFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_enum_category'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='enumCategory',
        )

        delete_kb_func.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStackResources"
                ],
                resources=['*']
            )
        )

        capture_workflow_errors_func = _lambda_python.PythonFunction(
            self, 'CaptureWorkflowErrorsFunc',
            runtime=runtime,
            architecture=arch,
            index='index.py',
            handler='handler',
            entry='assets/lambda/func_capture_workflow_orchestration_errors',
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='captureWorkflowOrchestrationErrors',
            environment={
                'TABLE_ANALYSIS': analysis_table.table_name
            }
        )

        capture_workflow_errors_func.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:GetDurableExecution"],
                resources=[f'{orchestrator_func.function_arn}:$LATEST'],
            )
        )

        list_tenders_func = _lambda.Function(
            self, 'ListTendersFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_list_tenders'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='listHistoricalTenders',
            environment={
                'BUCKET': historic_files_bucket.bucket_name
            }
        )

        historic_files_bucket.grant_read(list_tenders_func)

        for fn in [orchestrator_func, orchestrator_trigger_func, get_analysis_func,
                   scan_analysis_func, delete_kb_func, capture_workflow_errors_func]:
            analysis_table.grant_read_write_data(fn)

        funcs = {
            'Orchestrator': orchestrator_func,
            'OrchestratorTrigger': orchestrator_trigger_func,
            'GenerateUploadUrl': generate_upload_url_func,
            'GenerateDownloadUrl': generate_download_url_func,
            'ScanAnalysis': scan_analysis_func,
            'GetAnalysis': get_analysis_func,
            'DeleteKb': delete_kb_func,
            'EnumCategory': enum_category_func,
            'ChunkFiles': chunk_files_func,
            'CaptureWorkflowErrors': capture_workflow_errors_func,
            'DeleteAnalysisFiles': delete_files_func,
            'SelectReferenceResponse': select_reference_response_func,
            'ListTenders': list_tenders_func
        }

        for _, fn in funcs.items():
            NagSuppressions.add_resource_suppressions(
                fn,
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "Managed policy is required.",
                    },
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "Wildcard implicit in L2 helper method.",
                    }
                ],
                apply_to_children=True
            )

        return funcs, layer

    def __create_func_consume_ddb_stream(self, analysis_table, connections_table_name, layer):
        runtime = _lambda.Runtime.PYTHON_3_14
        arch = _lambda.Architecture.ARM_64

        consume_ddb_stream_func = _lambda.Function(
            self, 'ConsumeDDBStreamFunc',
            runtime=runtime,
            architecture=arch,
            handler='index.handler',
            code=_lambda.Code.from_asset('assets/lambda/func_consume_ddb_stream'),
            layers=[layer],
            timeout=Duration.minutes(1),
            function_name='consumeDDBStream',
            environment={
                'CONNECTIONS_TABLE': connections_table_name
            },
        )

        consume_ddb_stream_func.add_event_source(
            event_sources.DynamoEventSource(
                analysis_table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=100,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3,
                bisect_batch_on_error=True,
            )
        )

        consume_ddb_stream_func.add_to_role_policy(iam.PolicyStatement(
            actions=["execute-api:ManageConnections"],
            resources=["arn:aws:execute-api:*:*:*/@connections/*"]
        ))

        consume_ddb_stream_func.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:GetRecords",
                    "dynamodb:GetShardIterator",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:DescribeTable"
                ],
                resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{connections_table_name}"],
            )
        )

        analysis_table.grant_stream_read(consume_ddb_stream_func)

        NagSuppressions.add_resource_suppressions(
            consume_ddb_stream_func,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Managed policy is required.",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard implicit in L2 helper method.",
                }
            ],
            apply_to_children=True
        )

    @staticmethod
    def __create_api_gateway_resources(funcs, api: apigateway.RestApi, authorizer):
        analysis_resource = api.root.add_resource('analysis')
        list_tenders_resource = api.root.add_resource('list-tenders')
        enum_categories_resource = api.root.add_resource('enum-categories')

        analysis_detail_resource = analysis_resource.add_resource('{analysisId}')
        get_input_files_resource = analysis_detail_resource.add_resource('input-files')
        get_response_files_resource = analysis_detail_resource.add_resource('response-files')
        start_analysis_resource = analysis_detail_resource.add_resource('start')
        upload_resource = analysis_detail_resource.add_resource('generate-upload-url')
        download_resource = analysis_detail_resource.add_resource('generate-download-url')
        delete_kb_resource = analysis_detail_resource.add_resource('kb')
        delete_files_resource = analysis_detail_resource.add_resource('delete-files')

        list_tenders_resource.add_method(
            'GET',
            apigateway.LambdaIntegration(funcs['ListTenders']),
            api_key_required=True,
            authorizer=authorizer
        )

        enum_categories_resource.add_method(
            'GET',
            apigateway.LambdaIntegration(funcs['EnumCategory']),
            api_key_required=True,
            authorizer=authorizer
        )

        analysis_resource.add_method(
            'GET',
            apigateway.LambdaIntegration(funcs['ScanAnalysis']),
            api_key_required=True,
            authorizer=authorizer
        )

        for resource in [analysis_detail_resource, get_input_files_resource, get_response_files_resource]:
            resource.add_method(
                'GET',
                apigateway.LambdaIntegration(funcs['GetAnalysis']),
                api_key_required=True,
                authorizer=authorizer
            )

        start_analysis_resource.add_method(
            'GET',
            apigateway.LambdaIntegration(funcs['OrchestratorTrigger']),
            api_key_required=True,
            authorizer=authorizer
        )

        upload_resource.add_method(
            'POST',
            apigateway.LambdaIntegration(funcs['GenerateUploadUrl']),
            api_key_required=True,
            authorizer=authorizer
        )

        download_resource.add_method(
            'GET',
            apigateway.LambdaIntegration(funcs['GenerateDownloadUrl']),
            api_key_required=True,
            authorizer=authorizer
        )

        delete_kb_resource.add_method(
            'DELETE',
            apigateway.LambdaIntegration(funcs['DeleteKb']),
            api_key_required=True,
            authorizer=authorizer
        )

        delete_files_resource.add_method(
            'POST',
            apigateway.LambdaIntegration(funcs['DeleteAnalysisFiles']),
            api_key_required=True,
            authorizer=authorizer,
        )

    def __create_capture_workflow_errors_rule(self, handler):
        rule = events.Rule(
            self,"DurableExecutionErrorsRule",
            description="Invoke a handler Lambda when a durable execution fails.",
            event_pattern=events.EventPattern(
                source=["aws.lambda"],
                detail_type=["Durable Execution Status Change"],
                detail={"status": ["FAILED", 'TIMED_OUT', 'STOPPED']},
            ),
        )

        rule.add_target(
            targets.LambdaFunction(
                handler,
                retry_attempts=0,
                max_event_age=Duration.hours(1)
            )
        )
