from aws_cdk import (
    aws_bedrock as bedrock,
    aws_opensearchserverless as aoss,
    CustomResource,
    Stack,
    Fn,
    CfnParameter, CfnOutput, RemovalPolicy,
)
from constructs import Construct


class KnowledgeBaseStack(Stack):
    __L1_CHUNKING_TOKENS = 8192
    __L2_CHUNKING_TOKENS = __L1_CHUNKING_TOKENS // 2
    __OVERLAP_TOKENS = int(__L1_CHUNKING_TOKENS * 0.1)
    __VECTOR_DIMENSIONS = 3072 # For Amazon Nova Multimodal Embeddings v1
    __PARSING_MODEL_ARN = 'arn:aws:bedrock:{}:{}:inference-profile/global.amazon.nova-2-lite-v1:0'

    def __init__(self, scope: Construct, construct_id: str, embedding_model_arn, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        suffix_param = CfnParameter(self, "Suffix", type="String", description="Name of the tender folder in lowercase letters.")
        s3_uri_param = CfnParameter(self, "S3URI", type="String", description="Name of the tender folder.")

        with open('assets/kb_parsing_prompt.txt') as fd:
            parsing_prompt = fd.read()

        # --------- Resources names definition --------- #
        oss_collection_name = Fn.sub("cl-${Suffix}")
        oss_index_name = Fn.sub("index-${Suffix}")
        kb_name = Fn.sub("kb-${Suffix}")
        data_source_name = Fn.sub("data-source-${Suffix}")
        inclusion_prefix = s3_uri_param.value_as_string + '/to_index/'

        # --------- Imports from CoreStack --------- #
        provider_service_token = Fn.import_value("AossIndexWaiterProviderServiceToken")
        kb_role_arn = Fn.import_value("KbRoleARN")
        input_bucket_arn = Fn.import_value("InputBucketARN")
        multimodal_bucket_name = Fn.import_value("MultimodalBucketName")

        # --------- KB related resources --------- #
        collection, index = self.__create_oss_collection(oss_collection_name, oss_index_name)
        index_waiter = self.__create_index_waiter(provider_service_token, collection, index)
        kb = self.__create_kb(kb_name, index_waiter, index, collection, kb_role_arn, embedding_model_arn, multimodal_bucket_name)
        ds = self.__create_data_source(data_source_name, kb, inclusion_prefix, input_bucket_arn, parsing_prompt)

        CfnOutput(
            self, "DataSourceId",
            value=ds.attr_data_source_id,
            export_name=f"{suffix_param.value_as_string}-DataSourceId",
        )

        CfnOutput(
            self, "KnowledgeBaseId",
            value=kb.attr_knowledge_base_id,
            export_name=f"{suffix_param.value_as_string}-KnowledgeBaseId",
        )

    def __create_oss_collection(self, collection_name, index_name):
        collection = aoss.CfnCollection(
            self, "OSSCollection",
            name=collection_name,
            type="VECTORSEARCH"
        )

        index = aoss.CfnIndex(
            self, "VectorIndex",
            collection_endpoint=collection.attr_collection_endpoint,
            index_name=index_name,
            settings=aoss.CfnIndex.IndexSettingsProperty(
                index=aoss.CfnIndex.IndexProperty(
                    knn=True
                )
            ),
            mappings=aoss.CfnIndex.MappingsProperty(
                properties={
                    "embedding": aoss.CfnIndex.PropertyMappingProperty(
                        type="knn_vector",
                        dimension=self.__VECTOR_DIMENSIONS,
                        method=aoss.CfnIndex.MethodProperty(
                            name="hnsw",
                            engine="faiss",
                            space_type="l2",
                            parameters=aoss.CfnIndex.ParametersProperty(
                                ef_construction=512,
                                m=16,
                            ),
                        ),
                    ),
                    "text": aoss.CfnIndex.PropertyMappingProperty(type="text"),
                    "metadata": aoss.CfnIndex.PropertyMappingProperty(type="text"),
                }
            ),
        )

        index.node.add_dependency(collection)

        return collection, index

    def __create_index_waiter(self, provider_service_token, collection, index):
        index_ready = CustomResource(
            self, "WaitForAossIndexReady",
            removal_policy=RemovalPolicy.DESTROY,
            service_token=provider_service_token,
            properties={
                "CollectionEndpoint": collection.attr_collection_endpoint,
                "IndexName": index.index_name,
            }
        )

        index_ready.node.add_dependency(index)

        return index_ready

    def __create_kb(self, kb_name, index_waiter, index, collection, kb_service_role_arn, embedding_model_arn, multimodal_bucket_name):
        kb = bedrock.CfnKnowledgeBase(
            self, 'KnowledgeBase',
            name=kb_name,
            role_arn=kb_service_role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type='VECTOR',
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                    supplemental_data_storage_configuration=bedrock.CfnKnowledgeBase.SupplementalDataStorageConfigurationProperty(
                        supplemental_data_storage_locations=[
                            bedrock.CfnKnowledgeBase.SupplementalDataStorageLocationProperty(
                                supplemental_data_storage_location_type="S3",
                                s3_location=bedrock.CfnKnowledgeBase.S3LocationProperty(
                                    uri=f's3://{multimodal_bucket_name}'
                                )
                            )
                        ]
                    )
                )
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type='OPENSEARCH_SERVERLESS',
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=collection.attr_arn,
                    vector_index_name=index.index_name,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        metadata_field="metadata",
                        text_field="text",
                        vector_field="embedding"
                    )
                )
            )
        )

        kb.node.add_dependency(index_waiter)

        return kb

    def __create_data_source(self, data_source_name, kb, inclusion_prefix, input_bucket_arn, parsing_prompt):
        data_source = bedrock.CfnDataSource(
            self, "KnowledgeBaseDataSource",
            name=data_source_name,
            knowledge_base_id=kb.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type='S3',
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=input_bucket_arn,
                    inclusion_prefixes=[inclusion_prefix]
                )
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="HIERARCHICAL",
                    hierarchical_chunking_configuration=bedrock.CfnDataSource.HierarchicalChunkingConfigurationProperty(
                        level_configurations=[
                            bedrock.CfnDataSource.HierarchicalChunkingLevelConfigurationProperty(
                                max_tokens=self.__L1_CHUNKING_TOKENS
                            ),
                            bedrock.CfnDataSource.HierarchicalChunkingLevelConfigurationProperty(
                                max_tokens=self.__L2_CHUNKING_TOKENS
                            )
                        ],
                        overlap_tokens=self.__OVERLAP_TOKENS
                    )
                ),
                parsing_configuration=bedrock.CfnDataSource.ParsingConfigurationProperty(
                    parsing_strategy="BEDROCK_FOUNDATION_MODEL",
                    bedrock_foundation_model_configuration=bedrock.CfnDataSource.BedrockFoundationModelConfigurationProperty(
                        model_arn=self.__PARSING_MODEL_ARN.format(Stack.of(self).region, Stack.of(self).account),
                        parsing_modality='MULTIMODAL',
                        parsing_prompt=bedrock.CfnDataSource.ParsingPromptProperty(
                            parsing_prompt_text=parsing_prompt
                        )
                    )
                ),
            ),
            data_deletion_policy="DELETE",
        )

        data_source.add_dependency(kb)

        return data_source
