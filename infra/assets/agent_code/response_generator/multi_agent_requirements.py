#!/usr/bin/env python3
"""
Multi-Agent Requirements Extraction System - AWS AgentCore Runtime Deployment.

This module implements a multi-agent system deployable to AWS Bedrock AgentCore Runtime:
1. Technical Agent - Extracts technical requirements from technical_specifications documents
2. Legal Agent - Extracts administrative requirements from legal_clauses documents
3. Combiner Agent - Combines results from both agents into final requirements
4. Response Generator - Generates tender responses for PDF reference documents

Uses Strands SDK Graph pattern for requirements extraction with AgentCore async task handling.
"""

import os
import sys
import json
import boto3
import asyncio
import logging
import importlib
import threading

from datetime import datetime
from typing import List

# =============================================================================
# FORCE RELOAD PROMPTS LIBRARY (ensures changes are always picked up)
# =============================================================================
# Clear cached module to force fresh import of prompts
if 'prompts_library' in sys.modules:
    del sys.modules['prompts_library']

import prompts_library
importlib.reload(prompts_library)

from prompts_library import (
    TECHNICAL_SYSTEM_PROMPT, 
    LEGAL_SYSTEM_PROMPT, 
    COMBINER_SYSTEM_PROMPT,
    RESPONSE_GENERATOR_SYSTEM_PROMPT,
    STANDALONE_RESPONSE_GENERATOR_SYSTEM_PROMPT
)

# Fix UTF-8 encoding for Spanish characters
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("strands").setLevel(logging.INFO)
logging.getLogger("botocore").setLevel(logging.WARNING)

from botocore.config import Config as BotocoreConfig
from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent.graph import GraphBuilder
from strands.types.content import ContentBlock

# Identifies this solution's AWS service API calls, including the Bedrock traffic
# the agents below generate. The user agent is supplied by the deployed stack.
SOLUTION_USER_AGENT = os.environ.get("USER_AGENT_STRING", "")
SOLUTION_CONFIG = BotocoreConfig(user_agent_extra=SOLUTION_USER_AGENT)

# BedrockModel only applies its own 120s read timeout when it builds the client
# config itself, so the timeout is restated here for the config we hand it.
BEDROCK_READ_TIMEOUT = 120
SOLUTION_BEDROCK_CONFIG = BotocoreConfig(
    user_agent_extra=SOLUTION_USER_AGENT,
    read_timeout=BEDROCK_READ_TIMEOUT
)

sqs = boto3.client("sqs", config=SOLUTION_CONFIG)

# =============================================================================
# CHECK FOR LOCAL MODE BEFORE IMPORTING AGENTCORE
# =============================================================================
# This allows the code to run locally without starting the AgentCore server
LOCAL_MODE = "--local" in sys.argv

# Initialize AgentCore only if not in local mode
app = None

if not LOCAL_MODE:
    try:
        from bedrock_agentcore.runtime import BedrockAgentCoreApp
        app = BedrockAgentCoreApp(debug=True)
    except ImportError:
        logger.warning("bedrock-agentcore not installed. AgentCore mode unavailable.")
        logger.warning("Install with: pip install bedrock-agentcore")

# =============================================================================
# MODEL CONFIGURATION (Hardcoded)
# =============================================================================
MULTI_AGENT_MODEL_ID = os.environ.get('MULTI_AGENT_MODEL_ID', "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
RESPONSE_GENERATOR_MODEL_ID = os.environ.get('RESPONSE_GENERATOR_MODEL_ID', "us.anthropic.claude-opus-4-5-20251101-v1:0")


# =============================================================================
# CUSTOM RETRIEVE TOOL WITH HYBRID SEARCH AND CATEGORY FILTER
# =============================================================================
def create_retrieve_tool(category: str):
    """Factory function to create category-specific retrieve tools."""
    
    @tool(name=f"retrieve_{category.lower().replace('_', '')}")
    def retrieve_category(
        text: str,
        numberOfResults: int = 100,
        score: float = 0.1,
        searchType: str = "HYBRID"
    ) -> str:
        f"""
        Retrieve from Knowledge Base filtering by category={category}.
        
        This tool searches ONLY documents with category='{category}' metadata.
        
        Args:
            text: The search query text
            numberOfResults: Maximum results to return (default: 100)
            score: Minimum relevance score threshold 0.0-1.0 (default: 0.1)
            searchType: "HYBRID" or "SEMANTIC" (default: "HYBRID")
        
        Returns:
            Formatted search results with scores, sources, and content
        """
        knowledge_base_id = os.getenv("KNOWLEDGE_BASE_ID")
        region_name = os.getenv("AWS_REGION", "us-east-1")
        
        logger.info(f"🔍 KB Retrieval - Category: {category}")
        logger.info(f"   Query: {text[:100]}{'...' if len(text) > 100 else ''}")
        logger.info(f"   numberOfResults: {numberOfResults}, score: {score}, searchType: {searchType}")
        
        config = BotocoreConfig(
            user_agent_extra=f"{SOLUTION_USER_AGENT} strands-agents-retrieve-{category.lower()}".strip()
        )
        client = boto3.client("bedrock-agent-runtime", region_name=region_name, config=config)
        
        try:
            vector_search_config = {
                "numberOfResults": numberOfResults,
                "overrideSearchType": searchType.upper(),
                "filter": {
                    "equals": {
                        "key": "category",
                        "value": category
                    }
                }
            }
            
            response = client.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": text},
                retrievalConfiguration={
                    "vectorSearchConfiguration": vector_search_config
                }
            )
            
            results = response.get("retrievalResults", [])
            filtered_results = [r for r in results if r.get("score", 0.0) >= score]
            
            logger.info(f"📥 Results: {len(results)} total, {len(filtered_results)} above score {score}")
            
            if not filtered_results:
                return f"No {category} results found above score threshold {score}."
            
            # Format results
            formatted = []
            for i, result in enumerate(filtered_results, 1):
                result_score = result.get("score", 0.0)
                content = result.get("content", {}).get("text", "")
                location = result.get("location", {})
                source_uri = location.get("s3Location", {}).get("uri", "Unknown")
                metadata = result.get("metadata", {})
                
                filename = source_uri.split("/")[-1] if "/" in source_uri else source_uri
                page_info = (
                    metadata.get("page") or 
                    metadata.get("pageNumber") or 
                    metadata.get("page_number") or
                    metadata.get("x-amz-bedrock-kb-chunk-page") or
                    "N/A"
                )
                
                entry = f"[Result {i}] Score: {result_score:.4f}\n"
                entry += f"Document: {filename}\n"
                entry += f"Page: {page_info}\n"
                entry += f"Source: {source_uri}\n"
                entry += f"Category: {metadata.get('category', 'N/A')}\n"
                if metadata:
                    other_meta = {k: v for k, v in metadata.items() if k != 'category'}
                    if other_meta:
                        entry += f"Other Metadata: {json.dumps(other_meta, ensure_ascii=False)}\n"
                entry += f"Content: {content}\n"
                formatted.append(entry)
            
            return f"Found {len(filtered_results)} {category} results:\n\n" + "\n---\n".join(formatted)
            
        except Exception as e:
            logger.error(f"Error retrieving {category} documents: {str(e)}")
            return f"Error retrieving {category} documents: {str(e)}"
    
    return retrieve_category


# Create category-specific tools
retrieve_technical = create_retrieve_tool("technical_specifications")
retrieve_technical_modifications = create_retrieve_tool("technical_specifications_modifications")
retrieve_legal = create_retrieve_tool("legal_clauses")


# =============================================================================
# S3 HELPER FUNCTIONS
# =============================================================================
def get_run_timestamp() -> str:
    """Generate a timestamp for the current run in format YYYY-MM-DD_HH-MM."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def get_filename_from_s3_uri(s3_uri: str) -> str:
    """Extract the filename from an S3 URI."""
    return s3_uri.split("/")[-1]


def sanitize_document_name(filename: str) -> str:
    """
    Sanitize document name for Bedrock ConverseStream API.
    
    Allowed characters: alphanumeric, whitespace, hyphens, parentheses, square brackets.
    Cannot have more than one consecutive whitespace.
    """
    import re
    
    name = filename.replace(".pdf", "").replace(".PDF", "")
    name = re.sub(r'[^\w\s\-\(\)\[\]]', '-', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    
    return name


def save_to_s3(
    content: str, 
    filename: str, 
    tender_id: str, 
    run_timestamp: str,
    subfolder: str = "requirements"
) -> str:
    """
    Save content to S3 bucket with organized folder structure.
    
    Folder structure: /{tender_id}/{run_timestamp}/{subfolder}/{filename}
    """
    bucket_name = os.getenv("OUTPUT_BUCKET")
    region = os.getenv("AWS_REGION", "us-east-1")
    
    key = f"{tender_id}/{run_timestamp}/{subfolder}/{filename}"
    
    s3_client = boto3.client("s3", region_name=region, config=SOLUTION_CONFIG)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown"
    )
    
    s3_uri = f"s3://{bucket_name}/{key}"
    logger.info(f"✓ Saved to: {s3_uri}")
    return s3_uri


def read_pdf_from_s3(s3_uri: str) -> bytes:
    """Read a PDF file from S3 and return its content as bytes."""
    region = os.getenv("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region, config=SOLUTION_CONFIG)
    
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    uri_parts = s3_uri[5:].split("/", 1)
    bucket_name = uri_parts[0]
    key = uri_parts[1] if len(uri_parts) > 1 else ""
    
    logger.info(f"📥 Reading PDF from S3: {s3_uri}")
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        pdf_bytes = response["Body"].read()
        size_mb = len(pdf_bytes) / (1024 * 1024)
        logger.info(f"   ✓ Read {size_mb:.2f} MB ({len(pdf_bytes):,} bytes)")
        return pdf_bytes
    except Exception as e:
        logger.error(f"   ❌ Error reading PDF: {str(e)}")
        raise


def read_text_from_s3(s3_uri: str) -> str:
    """Read a text/markdown file from S3 and return its content as string."""
    region = os.getenv("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region, config=SOLUTION_CONFIG)
    
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    uri_parts = s3_uri[5:].split("/", 1)
    bucket_name = uri_parts[0]
    key = uri_parts[1] if len(uri_parts) > 1 else ""
    
    logger.info(f"📥 Reading text file from S3: {s3_uri}")
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read().decode("utf-8")
        logger.info(f"   ✓ Read {len(content):,} characters")
        return content
    except Exception as e:
        logger.error(f"   ❌ Error reading file: {str(e)}")
        raise


def read_json_from_s3(s3_uri: str) -> dict:
    """Read a JSON file from S3 and return its content as dict."""
    region = os.getenv("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region, config=SOLUTION_CONFIG)
    
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    uri_parts = s3_uri[5:].split("/", 1)
    bucket_name = uri_parts[0]
    key = uri_parts[1] if len(uri_parts) > 1 else ""
    
    logger.info(f"📥 Reading JSON from S3: {s3_uri}")
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)
        logger.info(f"   ✓ Read JSON successfully")
        return data
    except Exception as e:
        logger.error(f"   ❌ Error reading JSON: {str(e)}")
        raise


def load_response_uris_from_s3(response_uris_s3_uri: str) -> List[str]:
    """Load response URIs JSON from S3 and return list of PDF URIs."""
    data = read_json_from_s3(response_uris_s3_uri)
    pdf_uris = data.get("ResponseURIS", [])
    logger.info(f"   ✓ Found {len(pdf_uris)} PDF URIs")
    return pdf_uris


def copy_pdf_to_reference_folder(
    source_s3_uri: str,
    tender_id: str,
    run_timestamp: str
) -> str:
    """
    Copy a PDF from source location to the reference_pdfs folder.
    
    Args:
        source_s3_uri: Source S3 URI of the PDF
        tender_id: The tender identifier
        run_timestamp: Run timestamp for folder organization
    
    Returns:
        S3 URI of the copied PDF in the reference_pdfs folder
    """
    output_bucket = os.getenv("OUTPUT_BUCKET")
    region = os.getenv("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region, config=SOLUTION_CONFIG)
    
    # Parse source URI
    if not source_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {source_s3_uri}")
    
    source_parts = source_s3_uri[5:].split("/", 1)
    source_bucket = source_parts[0]
    source_key = source_parts[1] if len(source_parts) > 1 else ""
    
    # Extract filename from source
    filename = get_filename_from_s3_uri(source_s3_uri)
    
    # Build destination key
    dest_key = f"{tender_id}/{run_timestamp}/reference_pdfs/{filename}"
    
    logger.info(f"📋 Copying PDF to reference folder: {filename}")
    
    try:
        # Copy the object
        copy_source = {"Bucket": source_bucket, "Key": source_key}
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=output_bucket,
            Key=dest_key
        )
        
        dest_uri = f"s3://{output_bucket}/{dest_key}"
        logger.info(f"   ✓ Copied to: {dest_uri}")
        return dest_uri
        
    except Exception as e:
        logger.error(f"   ❌ Error copying PDF: {str(e)}")
        raise


def copy_all_reference_pdfs(
    pdf_uris: List[str],
    tender_id: str,
    run_timestamp: str
) -> List[dict]:
    """
    Copy all reference PDFs to the reference_pdfs folder.
    
    Args:
        pdf_uris: List of source S3 URIs for PDFs
        tender_id: The tender identifier
        run_timestamp: Run timestamp for folder organization
    
    Returns:
        List of dictionaries with copy results
    """
    logger.info(f"📁 Copying {len(pdf_uris)} reference PDFs to reference_pdfs folder...")
    
    results = []
    for pdf_uri in pdf_uris:
        try:
            dest_uri = copy_pdf_to_reference_folder(pdf_uri, tender_id, run_timestamp)
            results.append({
                "status": "success",
                "source_uri": pdf_uri,
                "dest_uri": dest_uri,
                "filename": get_filename_from_s3_uri(pdf_uri)
            })
        except Exception as e:
            results.append({
                "status": "failed",
                "source_uri": pdf_uri,
                "filename": get_filename_from_s3_uri(pdf_uri),
                "error": str(e)
            })
    
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    logger.info(f"   ✓ Reference PDFs copied: {successes} succeeded, {failures} failed")
    
    return results


# =============================================================================
# AGENT INITIALIZATION
# =============================================================================
def create_agents(region_name: str = "us-east-1"):
    """Create and initialize all agents for the multi-agent system."""
    
    logger.info("=" * 80)
    logger.info("INITIALIZING MULTI-AGENT REQUIREMENTS EXTRACTION SYSTEM")
    logger.info("=" * 80)
    
    # Model configuration
    model = BedrockModel(
        model_id=MULTI_AGENT_MODEL_ID,
        region_name=region_name,
        boto_client_config=SOLUTION_BEDROCK_CONFIG
    )
    
    # Technical Specifications Agent
    technical_agent = Agent(
        model=model,
        tools=[retrieve_technical, retrieve_technical_modifications],
        system_prompt=TECHNICAL_SYSTEM_PROMPT,
        name="Technical_Specifications_Agent"
    )
    logger.info("✓ Technical Specifications Agent initialized")
    
    # Legal Clauses Agent
    legal_agent = Agent(
        model=model,
        tools=[retrieve_legal],
        system_prompt=LEGAL_SYSTEM_PROMPT,
        name="Legal_Clauses_Agent"
    )
    logger.info("✓ Legal Clauses Agent initialized")
    
    # Combiner Agent
    combiner_agent = Agent(
        model=model,
        tools=[],
        system_prompt=COMBINER_SYSTEM_PROMPT,
        name="Requirements_Combiner_Agent"
    )
    logger.info("✓ Combiner Agent initialized")
    
    # Response Generator Model
    response_generator_model = BedrockModel(
        model_id=RESPONSE_GENERATOR_MODEL_ID,
        region_name=region_name,
        boto_client_config=SOLUTION_BEDROCK_CONFIG
    )
    logger.info("✓ Response Generator Model configured")
    
    return {
        "technical_agent": technical_agent,
        "legal_agent": legal_agent,
        "combiner_agent": combiner_agent,
        "response_generator_model": response_generator_model,
        "model": model
    }


def create_response_generator_agent(pdf_name: str, response_generator_model) -> Agent:
    """Factory to create a response generator agent for a specific PDF."""
    sanitized_name = sanitize_document_name(pdf_name).replace(" ", "_")[:50]
    return Agent(
        model=response_generator_model,
        tools=[],
        system_prompt=RESPONSE_GENERATOR_SYSTEM_PROMPT,
        name=f"Response_Generator_{sanitized_name}",
        callback_handler=None
    )


# =============================================================================
# BUILD MULTI-AGENT GRAPH FOR REQUIREMENTS EXTRACTION
# =============================================================================
def build_requirements_graph(technical_agent, legal_agent, combiner_agent):
    """Build the multi-agent graph for requirements extraction."""
    
    builder = GraphBuilder()
    
    # Add nodes (agents)
    technical_node = builder.add_node(technical_agent, node_id="technical_extractor")
    legal_node = builder.add_node(legal_agent, node_id="legal_extractor")
    combiner_node = builder.add_node(combiner_agent, node_id="combiner")
    
    # Add edges: Technical and Legal both feed into Combiner
    builder.add_edge(technical_node, combiner_node)
    builder.add_edge(legal_node, combiner_node)
    
    # Set entry points (both start simultaneously)
    builder.set_entry_point("technical_extractor")
    builder.set_entry_point("legal_extractor")
    
    # Build configuration
    builder.set_graph_id("tender_requirements_graph")
    builder.set_execution_timeout(600)  # 10 minutes max
    
    return builder.build()


# =============================================================================
# PARALLEL RESPONSE GENERATION (Phase 2)
# =============================================================================
async def generate_single_response_async(
    pdf_s3_uri: str,
    requirements_text: str,
    tender_id: str,
    run_timestamp: str,
    response_generator_model
) -> dict:
    """Generate a single tender response for one PDF reference document."""
    reference_filename = get_filename_from_s3_uri(pdf_s3_uri)
    
    try:
        logger.info(f"🔄 [{reference_filename}] Starting response generation...")
        
        pdf_bytes = read_pdf_from_s3(pdf_s3_uri)
        document_name = sanitize_document_name(reference_filename)
        agent = create_response_generator_agent(reference_filename, response_generator_model)
        
        task_prompt = f"""Generate a comprehensive tender response section based on:

## TASK
Based on the requirements document below and the reference PDF document provided, generate a professional tender response section.

## REQUIREMENTS DOCUMENT (Markdown)
```markdown
{requirements_text}
```

## REFERENCE DOCUMENT
The attached PDF is a reference document from a previous successful tender response. 
- This is ONE section/module from a complete tender response
- Study its structure, format, level of detail, and professional language
- Adapt the style and approach for the NEW requirements above
- Do NOT copy specific content - use it as a template for structure and tone

## OUTPUT INSTRUCTIONS
1. Generate a complete tender response section in Markdown format
2. **IMPORTANT: Write the ENTIRE output in Spanish** (translate any English content)
3. Address requirements from the requirements document that are RELEVANT to this section
4. Follow the structure pattern observed in the reference PDF
5. Include specific commitments, timelines, and resources
6. Add a compliance matrix mapping requirements to responses
7. Include added value propositions beyond minimum requirements

## LANGUAGE REQUIREMENT
The output MUST be written in Spanish.

Generate the tender response now in Spanish:
"""
        
        content_blocks = [
            ContentBlock(
                document={
                    "format": "pdf",
                    "name": document_name,
                    "source": {
                        "bytes": pdf_bytes
                    }
                }
            ),
            ContentBlock(
                text=task_prompt
            )
        ]
        
        agent_result = await agent.invoke_async(content_blocks)
        generated_response = str(agent_result)
        logger.info(f"   ✓ [{reference_filename}] Generated {len(generated_response):,} characters")
        
        timestamp_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_header = f"""# Tender Response - {reference_filename}

**Tender ID:** {tender_id}
**Generated:** {timestamp_display}
**Run Timestamp:** {run_timestamp}
**Reference Document:** {reference_filename}
**Generation Method:** Strands Agent with Native PDF Document Support

---

"""
        
        final_response = response_header + generated_response
        output_filename = f"{tender_id}_{reference_filename}.md"
        response_uri = save_to_s3(
            final_response,
            output_filename,
            tender_id,
            run_timestamp,
            subfolder="responses"
        )
        
        logger.info(f"   ✓ [{reference_filename}] Response saved successfully")
        
        return {
            "status": "success",
            "pdf_uri": pdf_s3_uri,
            "pdf_filename": reference_filename,
            "output_uri": response_uri,
            "characters": len(generated_response)
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"   ❌ [{reference_filename}] FAILED: {error_msg}")
        
        return {
            "status": "failed",
            "pdf_uri": pdf_s3_uri,
            "pdf_filename": reference_filename,
            "error": error_msg
        }


async def generate_all_responses_parallel(
    pdf_uris: List[str],
    requirements_text: str,
    tender_id: str,
    run_timestamp: str,
    response_generator_model
) -> List[dict]:
    """Generate tender responses for all PDF reference documents in parallel."""
    logger.info(f"PARALLEL RESPONSE GENERATION - {len(pdf_uris)} PDFs")
    
    tasks = [
        generate_single_response_async(uri, requirements_text, tender_id, run_timestamp, response_generator_model)
        for uri in pdf_uris
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "status": "failed",
                "pdf_uri": pdf_uris[i],
                "pdf_filename": get_filename_from_s3_uri(pdf_uris[i]),
                "error": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results


def run_parallel_response_generation(
    pdf_uris: List[str],
    requirements_text: str,
    tender_id: str,
    run_timestamp: str,
    response_generator_model
) -> List[dict]:
    """Synchronous wrapper to run parallel response generation."""
    return asyncio.run(
        generate_all_responses_parallel(pdf_uris, requirements_text, tender_id, run_timestamp, response_generator_model)
    )


# =============================================================================
# STANDALONE RESPONSE GENERATION (No Reference PDFs)
# =============================================================================
def generate_standalone_response(
    requirements_text: str,
    tender_id: str,
    run_timestamp: str,
    response_generator_model
) -> dict:
    """Generate a complete tender response when no reference PDFs are available."""
    logger.info("STANDALONE RESPONSE GENERATION (No Reference PDFs)")
    logger.info("📝 Generating complete tender response from requirements only...")
    
    try:
        agent = Agent(
            model=response_generator_model,
            tools=[],
            system_prompt=STANDALONE_RESPONSE_GENERATOR_SYSTEM_PROMPT,
            name="Standalone_Response_Generator",
            callback_handler=None
        )
        
        task_prompt = f"""Generate a COMPLETE tender response based on the requirements document below.

## REQUIREMENTS DOCUMENT
```markdown
{requirements_text}
```

## INSTRUCTIONS
1. Analyze the requirements document to identify:
   - Evaluation criteria and their weights
   - Required response structure/index (if specified)
   - Page limits per section
   - Technical specifications to address

2. Generate a complete tender response that:
   - Follows any index structure found in the requirements
   - Creates sections that map to evaluation criteria
   - Addresses all technical and administrative requirements
   - Includes specific commitments, timelines, and resources
   - Adds value propositions beyond minimum requirements

3. Include:
   - Title page with tender identification
   - Table of contents
   - All required sections with substantive content
   - Compliance matrix (if applicable)

Generate the complete tender response now:
"""
        
        logger.info("🔄 Invoking standalone response generator...")
        agent_result = agent(task_prompt)
        
        generated_response = str(agent_result)
        logger.info(f"   ✓ Generated {len(generated_response):,} characters")
        
        timestamp_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_header = f"""# Complete Tender Response

**Tender ID:** {tender_id}
**Generated:** {timestamp_display}
**Run Timestamp:** {run_timestamp}
**Generation Method:** Standalone (No Reference PDFs - Structure derived from requirements)

---

"""
        
        final_response = response_header + generated_response
        output_filename = f"{tender_id}_complete_response.md"
        response_uri = save_to_s3(
            final_response,
            output_filename,
            tender_id,
            run_timestamp,
            subfolder="responses"
        )
        
        logger.info(f"   ✓ Response saved successfully")
        
        return {
            "status": "success",
            "output_uri": response_uri,
            "characters": len(generated_response),
            "generation_type": "standalone"
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"   ❌ FAILED: {error_msg}")
        
        return {
            "status": "failed",
            "error": error_msg,
            "generation_type": "standalone"
        }


# =============================================================================
# REQUIREMENTS EXTRACTION (Phase 1)
# =============================================================================
def extract_requirements(tender_id: str, run_timestamp: str, agents: dict) -> dict:
    """Execute the multi-agent requirements extraction workflow."""
    
    logger.info(f"EXTRACTING REQUIREMENTS FOR TENDER: {tender_id}")
    logger.info(f"RUN TIMESTAMP: {run_timestamp}")
    
    timestamp_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build the graph
    graph = build_requirements_graph(
        agents["technical_agent"],
        agents["legal_agent"],
        agents["combiner_agent"]
    )
    logger.info("✓ Multi-agent graph built successfully")
    logger.info("  - Entry points: technical_extractor, legal_extractor (parallel)")
    logger.info("  - Flow: [Technical] → [Combiner] ← [Legal]")
    
    # Execute the graph
    task = f"""Extract ALL requirements from tender documents for Tender ID: {tender_id}.

Technical Agent: Search and extract all technical requirements from technical_specifications documents.
Administrative Agent: Search and extract all administrative requirements from legal_clauses documents.

Use comprehensive search queries to find:
- All specifications
- All requirements
- All deadlines
- All budget information
- All solvency requirements
- All documentation requirements
"""
    
    logger.info("🔄 Executing multi-agent workflow...")
    
    try:
        result = graph(task)
        
        logger.info("EXECUTION COMPLETED")
        logger.info(f"Status: {result.status}")
        logger.info(f"Nodes completed: {result.completed_nodes}/{result.total_nodes}")
        logger.info(f"Execution order: {[n.node_id for n in result.execution_order]}")
        
        # Extract results from each node
        technical_result = ""
        legal_result = ""
        final_result = ""
        
        for node_id, node_result in result.results.items():
            agent_results = node_result.get_agent_results()
            for ar in agent_results:
                text = str(ar)
                if node_id == "technical_extractor":
                    technical_result = text
                elif node_id == "legal_extractor":
                    legal_result = text
                elif node_id == "combiner":
                    final_result = text
        
        # Save to S3
        logger.info("SAVING RESULTS TO S3")
        
        technical_header = f"""# Technical Specifications Requirements

**Tender ID:** {tender_id}
**Generated:** {timestamp_display}
**Run Timestamp:** {run_timestamp}
**Source:** technical_specifications Category Documents

---

"""
        legal_header = f"""# Legal Clauses Requirements

**Tender ID:** {tender_id}
**Generated:** {timestamp_display}
**Run Timestamp:** {run_timestamp}
**Source:** legal_clauses Category Documents

---

"""
        final_header = f"""# Complete Tender Requirements

**Tender ID:** {tender_id}
**Generated:** {timestamp_display}
**Run Timestamp:** {run_timestamp}
**Extraction Method:** Multi-Agent System (technical_specifications + legal_clauses → Combined)

---

"""
        
        uris = {}
        uris["run_timestamp"] = run_timestamp
        uris["technical"] = save_to_s3(
            technical_header + technical_result, 
            f"{tender_id}_technical_specifications_requirements.md", 
            tender_id, 
            run_timestamp,
            subfolder="requirements"
        )
        uris["legal"] = save_to_s3(
            legal_header + legal_result, 
            f"{tender_id}_legal_clauses_requirements.md", 
            tender_id, 
            run_timestamp,
            subfolder="requirements"
        )
        uris["final"] = save_to_s3(
            final_header + final_result, 
            f"{tender_id}_final_requirements.md", 
            tender_id, 
            run_timestamp,
            subfolder="requirements"
        )
        
        logger.info("✓ ALL REQUIREMENTS EXTRACTED AND SAVED")
        
        return uris
        
    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        raise




# =============================================================================
# MAIN WORKFLOW EXECUTION
# =============================================================================
def execute_workflow(payload: dict) -> dict:
    """
    Execute the complete tender response generation workflow.
    
    Args:
        payload: Dictionary containing:
            - tender_id: The tender identifier
            - knowledge_base_id: ID of the Bedrock Knowledge Base
            - output_bucket: S3 bucket for output files
            - response_uris_s3_uri: S3 URI to the response_uris.json file (optional)
            - aws_region: AWS region (default: us-east-1)
            - min_score: Minimum score for KB retrieval (default: 0.1)
            - number_of_results: Number of results for KB retrieval (default: 50)
    
    Returns:
        Dictionary with workflow results including URIs and status
    """
    # Set environment variables from payload
    os.environ["KNOWLEDGE_BASE_ID"] = payload.get("knowledge_base_id", "")
    os.environ["AWS_REGION"] = payload.get("aws_region", "us-east-1")
    os.environ["OUTPUT_BUCKET"] = payload.get("output_bucket", "")
    os.environ["MIN_SCORE"] = str(payload.get("min_score", 0.1))
    os.environ["NUMBER_OF_RESULTS"] = str(payload.get("number_of_results", 50))
    
    tender_id = payload.get("tender_id")
    response_uris_s3_uri = payload.get("response_uris_s3_uri", "")
    region_name = payload.get("aws_region", "us-east-1")
    
    run_timestamp = get_run_timestamp()
    
    logger.info("=" * 80)
    logger.info("TENDER RESPONSE GENERATION WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"Tender ID: {tender_id}")
    logger.info(f"Run Timestamp: {run_timestamp}")
    logger.info(f"Output folder: /{tender_id}/{run_timestamp}/")
    
    # Initialize agents
    agents = create_agents(region_name=region_name)
    
    # Phase 1: Extract Requirements
    result_uris = extract_requirements(tender_id, run_timestamp, agents)
    
    # Phase 2: Generate Responses
    logger.info("PHASE 2: TENDER RESPONSE GENERATION")
    
    # Load PDF URIs from S3 (if provided)
    pdf_uris = []
    if response_uris_s3_uri:
        try:
            logger.info("📋 Loading reference PDF URIs...")
            pdf_uris = load_response_uris_from_s3(response_uris_s3_uri)
            logger.info(f"📄 Reference PDFs to process: {len(pdf_uris)}")
        except Exception as e:
            logger.warning(f"Could not load response URIs: {str(e)}")
    
    # Load final requirements text
    logger.info("📖 Loading final requirements...")
    final_requirements_text = read_text_from_s3(result_uris["final"])
    
    # Check if we have reference PDFs or need standalone generation
    reference_pdfs_copy_results = []
    if not pdf_uris:
        logger.info("⚠️  No reference PDFs found - using standalone response generation")
        standalone_result = generate_standalone_response(
            requirements_text=final_requirements_text,
            tender_id=tender_id,
            run_timestamp=run_timestamp,
            response_generator_model=agents["response_generator_model"]
        )
        response_results = [standalone_result]
    else:
        # Copy reference PDFs to reference_pdfs folder
        logger.info("📁 COPYING REFERENCE PDFs TO OUTPUT BUCKET")
        reference_pdfs_copy_results = copy_all_reference_pdfs(
            pdf_uris=pdf_uris,
            tender_id=tender_id,
            run_timestamp=run_timestamp
        )
        
        logger.info(f"🚀 Starting parallel response generation for {len(pdf_uris)} PDFs...")
        response_results = run_parallel_response_generation(
            pdf_uris=pdf_uris,
            requirements_text=final_requirements_text,
            tender_id=tender_id,
            run_timestamp=run_timestamp,
            response_generator_model=agents["response_generator_model"]
        )
    
    # Build summary
    successes = [r for r in response_results if r["status"] == "success"]
    failures = [r for r in response_results if r["status"] == "failed"]
    
    logger.info("=" * 80)
    logger.info("EXECUTION COMPLETE - SUMMARY")
    logger.info("=" * 80)
    logger.info(f"📊 Results: {len(successes)} succeeded, {len(failures)} failed")
    
    # Build reference PDFs copy summary
    ref_copy_successes = [r for r in reference_pdfs_copy_results if r["status"] == "success"]
    ref_copy_failures = [r for r in reference_pdfs_copy_results if r["status"] == "failed"]
    
    return {
        "status": "success" if not failures else "partial_success" if successes else "failed",
        "tender_id": tender_id,
        "run_timestamp": run_timestamp,
        "requirements_uris": result_uris,
        "response_results": response_results,
        "reference_pdfs_copy_results": reference_pdfs_copy_results,
        "summary": {
            "total": len(response_results),
            "succeeded": len(successes),
            "failed": len(failures),
            "reference_pdfs_copied": len(ref_copy_successes),
            "reference_pdfs_copy_failed": len(ref_copy_failures)
        }
    }


def send_to_queue(task_id, success, error=None, response=None):
    body = {
        "Id": task_id,
        "Success": success,
        'CreatedAt': datetime.now().isoformat()
    }

    if error:
        body['Error'] = error

    if response:
        body['Response'] = response

    sqs.send_message(
        QueueUrl=os.environ['RUNTIME_INVOCATIONS_QUEUE_URL'],
        MessageBody=json.dumps(body),
    )


# =============================================================================
# AGENTCORE ENTRYPOINTS (only registered when app is available)
# =============================================================================
def register_agentcore_entrypoints():
    """Register AgentCore entrypoints. Only called when app is available."""
    
    @app.entrypoint
    def invoke(payload: dict):
        """
        AgentCore Runtime entrypoint for the multi-agent tender response system.
        
        This is a synchronous entrypoint that executes the workflow and returns
        the result directly. For long-running operations, the AgentCore Runtime
        handles the connection management.
        
        Args:
            payload: Dictionary containing workflow parameters
        
        Returns:
            Dictionary with workflow results
        """
        logger.info("=" * 80)
        logger.info("AGENTCORE INVOCATION RECEIVED")
        logger.info("=" * 80)
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")

        task_id = app.add_async_task('process_request')

        def work():
            try:
                # Execute workflow directly and return result
                result = execute_workflow(payload)
                logger.info("Workflow completed successfully")
                send_to_queue(task_id, True, response=result)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Workflow failed: {error_msg}")
                send_to_queue(task_id, False, error=error_msg)
            finally:
                app.complete_async_task(task_id)

        threading.Thread(target=work, daemon=True).start()

        return {'TaskId': task_id}


# Register entrypoints if app is available (not in local mode)
if app is not None:
    register_agentcore_entrypoints()


# =============================================================================
# LOCAL EXECUTION (for testing)
# =============================================================================
if __name__ == "__main__":
    if LOCAL_MODE:
        # Local testing mode - run workflow directly
        logger.info("=" * 80)
        logger.info("Running in LOCAL TESTING mode")
        logger.info("=" * 80)
        
        payload = {
            "tender_id": "your-tender-id",
            "knowledge_base_id": "YOUR_KB_ID",
            "response_uris_s3_uri": "s3://your-input-bucket/your-tender-id/response_uris.json",
            "output_bucket": "your-output-bucket",
            "aws_region": "us-east-1",
            "min_score": 0.1,
            "number_of_results": 50,
        }
        
        result = execute_workflow(payload)
        logger.info("=" * 80)
        logger.info("WORKFLOW COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Result: {json.dumps(result, indent=2)}")
    elif app is not None:
        # AgentCore Runtime mode
        logger.info("Starting AgentCore Runtime server on port 8080")
        app.run()
    else:
        # Error: bedrock-agentcore not installed and not in local mode
        logger.error("=" * 80)
        logger.error("ERROR: Cannot start AgentCore server")
        logger.error("=" * 80)
        logger.error("The 'bedrock-agentcore' package is not installed.")
        logger.error("")
        logger.error("To run locally for testing, use:")
        logger.error("  python multi_agent_requirements.py --local")
        logger.error("")
        logger.error("To run in AgentCore mode, install the package:")
        logger.error("  pip install bedrock-agentcore")
        sys.exit(1)
