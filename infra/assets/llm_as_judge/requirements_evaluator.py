"""
Requirements Extraction Evaluator v2 - Custom LLM-as-Judge

A purpose-built evaluator for assessing how well a multi-agent system 
extracted requirements from tender documents, using direct LLM evaluation.

Key Features:
- Direct LLM-as-Judge with domain-specific prompts
- Full document context (no chunking/RAG - leverages modern LLM context windows)
- Structured scoring rubrics (presence, completeness, accuracy)
- Detailed reasoning for each evaluation
- Timestamped output folders with input file copies
- S3 support for input files

Usage:
    python requirements_evaluator.py

Output: evaluation_report.json and evaluation_report.md with per-requirement scores and overall metrics.
"""

import os
import sys
import json
import io
from datetime import datetime
from dataclasses import dataclass, field

import pandas as pd
import math

# =============================================================================
# CONFIGURATION
# =============================================================================
# TODO: Update these paths with your own ground-truth and generated requirement files.
GROUND_TRUTH_CSV_PATH = "s3://your-output-bucket/LLM_AS_JUDGE/ground_truth_requirements.csv"
GENERATED_REQUIREMENTS_PATH = "s3://your-output-bucket/your-tender-id/requirements/final_requirements.md"
AWS_REGION = "us-east-1"
AWS_PROFILE = None
EVALUATOR_LLM_MODEL = "global.anthropic.claude-opus-4-5-20251101-v1:0"

# S3 Output Configuration
OUTPUT_S3_URI = "s3://your-output-bucket/LLM_AS_JUDGE/Final_Requirements"

# Local Output Configuration
SAVE_LOCALLY = False  # Set to True to also save outputs locally next to this script

# Output filenames (will be placed in timestamped folder)
OUTPUT_REPORT_JSON = "evaluation_report.json"
OUTPUT_REPORT_MD = "evaluation_report.md"


# =============================================================================
# HELPERS
# =============================================================================
def get_run_timestamp() -> str:
    """Generate a timestamp for the current run in format YYYY-MM-DD_HH-MM."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


def get_script_directory() -> str:
    """Get the directory where this script is located."""
    return os.path.dirname(os.path.abspath(__file__))


def create_output_directory(run_timestamp: str) -> str:
    """
    Create a timestamped output directory next to this script.
    
    Returns the full path to the created directory.
    """
    script_dir = get_script_directory()
    output_dir = os.path.join(script_dir, run_timestamp)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def is_s3_path(path: str) -> bool:
    """Check if a path is an S3 URI."""
    return path.startswith("s3://")


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """
    Parse an S3 URI into bucket and key.
    
    Args:
        s3_uri: S3 URI in format s3://bucket/key
        
    Returns:
        Tuple of (bucket_name, key)
    """
    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")
    
    uri_parts = s3_uri[5:].split("/", 1)
    bucket_name = uri_parts[0]
    key = uri_parts[1] if len(uri_parts) > 1 else ""
    return bucket_name, key


def get_filename_from_path(path: str) -> str:
    """Extract filename from a local path or S3 URI."""
    if is_s3_path(path):
        return path.split("/")[-1]
    return os.path.basename(path)


def read_text_from_s3(s3_uri: str) -> str:
    """Read a text file from S3 and return its content as string."""
    import boto3
    
    bucket_name, key = parse_s3_uri(s3_uri)
    print(f"   📥 Reading from S3: {s3_uri}")
    
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    content = response["Body"].read().decode("utf-8")
    print(f"      ✓ Read {len(content):,} characters")
    return content


def read_csv_from_s3(s3_uri: str) -> bytes:
    """Read a CSV file from S3 and return as bytes."""
    import boto3
    
    bucket_name, key = parse_s3_uri(s3_uri)
    print(f"   📥 Reading CSV from S3: {s3_uri}")
    
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    csv_content = response["Body"].read()
    print(f"      ✓ Read {len(csv_content):,} bytes")
    return csv_content


def download_s3_file_to_local(s3_uri: str, local_path: str) -> str:
    """Download a file from S3 to a local path."""
    import boto3
    
    bucket_name, key = parse_s3_uri(s3_uri)
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    s3_client.download_file(bucket_name, key, local_path)
    return local_path


def upload_to_s3(content: str, s3_uri: str, content_type: str = "text/plain") -> str:
    """Upload text content to S3."""
    import boto3
    
    bucket_name, key = parse_s3_uri(s3_uri)
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType=content_type
    )
    return s3_uri


def copy_s3_to_s3(source_s3_uri: str, dest_s3_uri: str) -> str:
    """Copy a file from one S3 location to another."""
    import boto3
    
    source_bucket, source_key = parse_s3_uri(source_s3_uri)
    dest_bucket, dest_key = parse_s3_uri(dest_s3_uri)
    
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    copy_source = {"Bucket": source_bucket, "Key": source_key}
    s3_client.copy_object(CopySource=copy_source, Bucket=dest_bucket, Key=dest_key)
    return dest_s3_uri


def copy_input_files_to_s3(s3_output_prefix: str, ground_truth_path: str, generated_path: str) -> dict:
    """Copy the input files being evaluated to the S3 output directory."""
    copied_files = {}
    
    # Ensure prefix ends with /
    if not s3_output_prefix.endswith("/"):
        s3_output_prefix += "/"
    
    # Copy ground truth CSV
    gt_filename = get_filename_from_path(ground_truth_path)
    gt_dest_uri = f"{s3_output_prefix}ground_truth_{gt_filename}"
    
    if is_s3_path(ground_truth_path):
        copy_s3_to_s3(ground_truth_path, gt_dest_uri)
        copied_files["ground_truth"] = gt_dest_uri
        print(f"   ✓ Copied ground truth to S3: {gt_filename}")
    
    # Copy generated requirements MD
    gen_filename = get_filename_from_path(generated_path)
    gen_dest_uri = f"{s3_output_prefix}generated_{gen_filename}"
    
    if is_s3_path(generated_path):
        copy_s3_to_s3(generated_path, gen_dest_uri)
        copied_files["generated"] = gen_dest_uri
        print(f"   ✓ Copied generated requirements to S3: {gen_filename}")
    
    return copied_files


def copy_input_files_to_output(output_dir: str, ground_truth_path: str, generated_path: str) -> dict:
    """Copy the input files being evaluated to the local output directory."""
    copied_files = {}
    
    # Copy/download ground truth CSV
    gt_filename = get_filename_from_path(ground_truth_path)
    gt_dest = os.path.join(output_dir, f"ground_truth_{gt_filename}")
    
    if is_s3_path(ground_truth_path):
        download_s3_file_to_local(ground_truth_path, gt_dest)
        copied_files["ground_truth"] = gt_dest
        print(f"   ✓ Downloaded ground truth: {gt_filename}")
    elif os.path.exists(ground_truth_path):
        import shutil
        shutil.copy2(ground_truth_path, gt_dest)
        copied_files["ground_truth"] = gt_dest
        print(f"   ✓ Copied ground truth: {gt_filename}")
    
    # Copy/download generated requirements MD
    gen_filename = get_filename_from_path(generated_path)
    gen_dest = os.path.join(output_dir, f"generated_{gen_filename}")
    
    if is_s3_path(generated_path):
        download_s3_file_to_local(generated_path, gen_dest)
        copied_files["generated"] = gen_dest
        print(f"   ✓ Downloaded generated requirements: {gen_filename}")
    elif os.path.exists(generated_path):
        import shutil
        shutil.copy2(generated_path, gen_dest)
        copied_files["generated"] = gen_dest
        print(f"   ✓ Copied generated requirements: {gen_filename}")
    
    return copied_files


def check_file_exists(path: str) -> bool:
    """Check if a file exists (local or S3)."""
    if is_s3_path(path):
        import boto3
        try:
            bucket_name, key = parse_s3_uri(path)
            s3_client = boto3.client("s3", region_name=AWS_REGION)
            s3_client.head_object(Bucket=bucket_name, Key=key)
            return True
        except Exception:
            return False
    else:
        return os.path.exists(path)


def sanitize_float(value: float, default: float = 0.0) -> float:
    """Convert NaN/inf to a valid JSON-serializable number."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return default
    return float(value)


# =============================================================================
# DATA STRUCTURES
# =============================================================================
@dataclass
class Requirement:
    """Represents a ground truth requirement."""
    id: str
    type: str
    input_text: str
    expected_output: str
    business_rules: str
    reference_docs: str


@dataclass
class RequirementEvaluation:
    """Evaluation result for a single requirement."""
    requirement_id: str
    requirement_type: str
    expected_output: str
    
    # Evaluation scores (0.0 - 1.0)
    found: bool = False
    presence_score: float = 0.0
    completeness_score: float = 0.0
    accuracy_score: float = 0.0
    overall_score: float = 0.0
    
    # Extracted information
    matched_text: str = ""
    matched_section: str = ""
    
    # LLM reasoning
    reasoning: str = ""
    evaluation_confidence: float = 0.0


@dataclass
class EvaluationReport:
    """Overall evaluation report."""
    total_requirements: int = 0
    requirements_found: int = 0
    requirements_missed: int = 0
    
    # Aggregate scores
    avg_presence_score: float = 0.0
    avg_completeness_score: float = 0.0
    avg_accuracy_score: float = 0.0
    avg_overall_score: float = 0.0
    
    # Detailed results
    evaluations: list = field(default_factory=list)
    
    # Metadata
    evaluation_timestamp: str = ""
    evaluator_model: str = ""
    ground_truth_path: str = ""
    generated_path: str = ""


# =============================================================================
# FILE READERS
# =============================================================================
def read_ground_truth_csv(csv_path: str) -> list[Requirement]:
    """Read requirements from ground truth CSV file (local or S3)."""
    
    # Handle S3 paths
    if is_s3_path(csv_path):
        csv_bytes = read_csv_from_s3(csv_path)
        df_raw = pd.read_csv(io.BytesIO(csv_bytes), encoding='utf-8', header=None, nrows=10)
    else:
        df_raw = pd.read_csv(csv_path, encoding='utf-8', header=None, nrows=10)
    
    header_row = 0
    for i in range(len(df_raw)):
        row_str = str(df_raw.iloc[i].tolist())
        if 'ID Requisito' in row_str or 'ID' in row_str:
            header_row = i
            break
    
    # Read full CSV with detected header
    if is_s3_path(csv_path):
        csv_bytes = read_csv_from_s3(csv_path)
        df = pd.read_csv(io.BytesIO(csv_bytes), encoding='utf-8', header=header_row)
    else:
        df = pd.read_csv(csv_path, encoding='utf-8', header=header_row)
    
    df = df.dropna(how='all')
    
    column_mapping = {
        'ID Requisito': 'id',
        'Tipo de Requisito': 'type', 
        'Entrada (Input del Pliego)': 'input_text',
        'Salida (Output Deseado)': 'expected_output',
        'Reglas de Negocio / Lógica': 'business_rules',
        'Documentación de Referencia': 'reference_docs'
    }
    
    for orig, mapped in column_mapping.items():
        for col in df.columns:
            if orig.lower() in col.lower():
                df = df.rename(columns={col: mapped})
                break
    
    df = df.fillna('')
    
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    
    if 'id' not in df.columns:
        print("Warning: Could not find 'id' column")
        return []
    
    df = df[(df['id'] != '') & (df['id'] != 'nan')]
    
    requirements = []
    for _, row in df.iterrows():
        req = Requirement(
            id=str(row.get('id', '')),
            type=str(row.get('type', '')),
            input_text=str(row.get('input_text', '')),
            expected_output=str(row.get('expected_output', '')),
            business_rules=str(row.get('business_rules', '')),
            reference_docs=str(row.get('reference_docs', ''))
        )
        if req.expected_output and req.expected_output != 'nan':
            requirements.append(req)
    
    return requirements


def read_generated_requirements(md_path: str) -> str:
    """Read the generated requirements markdown file (local or S3)."""
    if is_s3_path(md_path):
        return read_text_from_s3(md_path)
    else:
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()


# =============================================================================
# LLM-AS-JUDGE EVALUATION (BATCH - Single LLM Call via boto3)
# =============================================================================
def call_bedrock_converse(prompt: str, model_id: str, region: str) -> str:
    """
    Call Bedrock Converse API directly using boto3 (no langchain needed).
    """
    import boto3
    
    client = boto3.client('bedrock-runtime', region_name=region)
    
    response = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        inferenceConfig={
            "temperature": 0.1,
            "maxTokens": 8000
        }
    )
    
    return response['output']['message']['content'][0]['text']


def evaluate_all_requirements_batch(
    requirements: list[Requirement],
    full_document: str
) -> list[RequirementEvaluation]:
    """
    Evaluate ALL requirements in a SINGLE LLM call using boto3 directly.
    No langchain dependency needed.
    """
    
    # Build requirements list for the prompt
    requirements_text = ""
    for i, req in enumerate(requirements, 1):
        requirements_text += f"""
### Requirement #{req.id}
- **Type:** {req.type}
- **Expected Output:** {req.expected_output}
- **Source Context:** {req.input_text[:300] if req.input_text else 'N/A'}
"""
    
    evaluation_prompt = f"""You are an expert evaluator assessing requirements extraction from Spanish tender documents.

## TASK
Evaluate ALL {len(requirements)} requirements below against the extracted document in a SINGLE pass.

## LANGUAGE HANDLING
- Expected requirements are in **SPANISH**
- Extracted document may be **SPANISH and/or ENGLISH**
- Evaluate **semantic equivalence** regardless of language
- Examples: "Aportar el DEUC" = "Submit DEUC" = "DEUC required"

## NEGATIVE REQUIREMENTS (ABSENCE = CORRECT)
Some requirements specify something is **NOT required**:
- "No se exige" / "No hay que aportar nada" / "No está marcado"
**If expected_output says NOT required AND document omits it → Score 1.0 (CORRECT)**

## REQUIREMENTS TO EVALUATE
{requirements_text}

## EXTRACTED DOCUMENT (Search thoroughly!)
{full_document}

## SCORING RUBRIC
- **Presence (0-1):** Is it there? 1.0=explicit, 0.7=implied, 0.3=tangential, 0=missing
- **Completeness (0-1):** All details captured? 1.0=all, 0.7=most, 0.5=some, 0=none
- **Accuracy (0-1):** Correct info? 1.0=exact, 0.7=minor diff, 0.5=partial, 0=wrong

## OUTPUT FORMAT (JSON array, no markdown):

[
  {{
    "requirement_id": "1",
    "found": true/false,
    "presence_score": 0.0-1.0,
    "completeness_score": 0.0-1.0,
    "accuracy_score": 0.0-1.0,
    "matched_text": "exact quote from document (or empty)",
    "matched_section": "section name/number (or empty)",
    "reasoning": "1-2 sentences"
  }},
  ... (one object per requirement)
]"""

    try:
        print("  🤖 Calling Bedrock (boto3) for all requirements...")
        response_text = call_bedrock_converse(
            prompt=evaluation_prompt,
            model_id=EVALUATOR_LLM_MODEL,
            region=AWS_REGION
        )
        
        # Parse JSON response
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]
        
        results = json.loads(response_text.strip())
        
        # Map results to RequirementEvaluation objects
        evaluations = []
        results_by_id = {str(r.get('requirement_id', '')): r for r in results}
        
        for req in requirements:
            result = results_by_id.get(req.id, {})
            
            overall = (
                result.get('presence_score', 0) * 0.3 +
                result.get('completeness_score', 0) * 0.4 +
                result.get('accuracy_score', 0) * 0.3
            )
            
            evaluations.append(RequirementEvaluation(
                requirement_id=req.id,
                requirement_type=req.type,
                expected_output=req.expected_output[:200] + "..." if len(req.expected_output) > 200 else req.expected_output,
                found=result.get('found', False),
                presence_score=sanitize_float(result.get('presence_score', 0)),
                completeness_score=sanitize_float(result.get('completeness_score', 0)),
                accuracy_score=sanitize_float(result.get('accuracy_score', 0)),
                overall_score=sanitize_float(overall),
                matched_text=result.get('matched_text', '')[:500],
                matched_section=result.get('matched_section', ''),
                reasoning=result.get('reasoning', ''),
                evaluation_confidence=0.8
            ))
        
        return evaluations
        
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse batch LLM response: {e}")
        return [
            RequirementEvaluation(
                requirement_id=req.id,
                requirement_type=req.type,
                expected_output=req.expected_output[:200],
                found=False,
                reasoning=f"Batch LLM response parsing failed: {str(e)}"
            )
            for req in requirements
        ]
    except Exception as e:
        print(f"Error in batch evaluation: {e}")
        return [
            RequirementEvaluation(
                requirement_id=req.id,
                requirement_type=req.type,
                expected_output=req.expected_output[:200],
                found=False,
                reasoning=f"Batch evaluation error: {str(e)}"
            )
            for req in requirements
        ]


# =============================================================================
# MAIN EVALUATION PIPELINE
# =============================================================================
def evaluate_all_requirements(
    requirements: list[Requirement],
    generated_document: str
) -> EvaluationReport:
    """
    Main evaluation pipeline: evaluate all requirements in a SINGLE LLM call.
    Uses boto3 directly - no langchain dependency.
    """
    print(f"📄 Document size: {len(generated_document):,} characters (~{len(generated_document)//4:,} tokens)")
    print(f"📋 Requirements: {len(requirements)}")
    
    # Evaluate ALL requirements in ONE boto3 call
    evaluations = evaluate_all_requirements_batch(requirements, generated_document)
    
    # Calculate aggregate scores
    found_count = sum(1 for e in evaluations if e.found)
    
    presence_scores = [e.presence_score for e in evaluations]
    completeness_scores = [e.completeness_score for e in evaluations]
    accuracy_scores = [e.accuracy_score for e in evaluations]
    overall_scores = [e.overall_score for e in evaluations]
    
    report = EvaluationReport(
        total_requirements=len(requirements),
        requirements_found=found_count,
        requirements_missed=len(requirements) - found_count,
        avg_presence_score=sum(presence_scores) / len(presence_scores) if presence_scores else 0,
        avg_completeness_score=sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0,
        avg_accuracy_score=sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0,
        avg_overall_score=sum(overall_scores) / len(overall_scores) if overall_scores else 0,
        evaluations=[
            {
                "requirement_id": e.requirement_id,
                "requirement_type": e.requirement_type,
                "expected_output": e.expected_output,
                "found": e.found,
                "presence_score": e.presence_score,
                "completeness_score": e.completeness_score,
                "accuracy_score": e.accuracy_score,
                "overall_score": e.overall_score,
                "matched_text": e.matched_text,
                "matched_section": e.matched_section,
                "reasoning": e.reasoning,
                "confidence": e.evaluation_confidence
            }
            for e in evaluations
        ],
        evaluation_timestamp=datetime.now().isoformat(),
        evaluator_model=EVALUATOR_LLM_MODEL,
        ground_truth_path=GROUND_TRUTH_CSV_PATH,
        generated_path=GENERATED_REQUIREMENTS_PATH
    )
    
    return report


# =============================================================================
# REPORT GENERATION
# =============================================================================
def print_report(report: EvaluationReport):
    """Print a formatted evaluation report to console."""
    print("\n" + "=" * 80)
    print("📊 REQUIREMENTS EXTRACTION EVALUATION REPORT (v2 - LLM-as-Judge)")
    print("=" * 80)
    
    print(f"\n📈 SUMMARY:")
    print(f"   Requirements Found:    {report.requirements_found}/{report.total_requirements} ({report.requirements_found/report.total_requirements*100:.1f}%)")
    print(f"   Requirements Missed:   {report.requirements_missed}")
    
    print(f"\n📊 AGGREGATE SCORES:")
    print(f"   Presence Score:        {report.avg_presence_score:.2%}")
    print(f"   Completeness Score:    {report.avg_completeness_score:.2%}")
    print(f"   Accuracy Score:        {report.avg_accuracy_score:.2%}")
    print(f"   Overall Score:         {report.avg_overall_score:.2%}")
    
    print(f"\n📋 DETAILED RESULTS:")
    print("-" * 80)
    
    for e in report.evaluations:
        status = "✅" if e["found"] else "❌"
        print(f"{e['requirement_id']:<6} {status} Overall: {e['overall_score']:.2f}  "
              f"P:{e['presence_score']:.2f} C:{e['completeness_score']:.2f} A:{e['accuracy_score']:.2f}")
        print(f"        Type: {e['requirement_type'][:60]}")
        if e["found"] and e["matched_section"]:
            print(f"        Found in: {e['matched_section']}")
        if e["reasoning"]:
            print(f"        Reason: {e['reasoning'][:100]}...")
        print()
    
    print("=" * 80 + "\n")


def save_markdown_report(report: EvaluationReport, output_path: str):
    """Generate a user-friendly Markdown report for non-technical stakeholders."""
    
    score = report.avg_overall_score
    if score >= 0.9:
        grade = "🏆 Excelente"
        grade_desc = "La extracción de requisitos es de alta calidad."
    elif score >= 0.75:
        grade = "✅ Bueno"
        grade_desc = "La mayoría de los requisitos fueron extraídos correctamente."
    elif score >= 0.6:
        grade = "⚠️ Aceptable"
        grade_desc = "Algunos requisitos necesitan revisión manual."
    elif score >= 0.4:
        grade = "🔶 Necesita Mejora"
        grade_desc = "Se recomienda revisión detallada del documento."
    else:
        grade = "❌ Insuficiente"
        grade_desc = "Requiere revisión completa y re-extracción."
    
    found_reqs = [e for e in report.evaluations if e["found"]]
    missed_reqs = [e for e in report.evaluations if not e["found"]]
    
    md = f"""# 📊 Informe de Evaluación de Requisitos

> **Fecha:** {datetime.now().strftime("%d/%m/%Y %H:%M")}  
> **Documento Evaluado:** `{os.path.basename(report.generated_path)}`

---

## 🎯 Resumen Ejecutivo

| Métrica | Resultado |
|---------|-----------|
| **Calificación General** | {grade} |
| **Puntuación** | **{score:.0%}** |
| **Requisitos Encontrados** | {report.requirements_found} de {report.total_requirements} ({report.requirements_found/report.total_requirements*100:.0f}%) |
| **Requisitos Faltantes** | {report.requirements_missed} |

### Interpretación
{grade_desc}

---

## 📈 Puntuaciones por Categoría

| Categoría | Puntuación | Significado |
|-----------|------------|-------------|
| **Presencia** | {report.avg_presence_score:.0%} | ¿Se encontró el requisito en el documento? |
| **Completitud** | {report.avg_completeness_score:.0%} | ¿Están todos los detalles incluidos? |
| **Precisión** | {report.avg_accuracy_score:.0%} | ¿La información es correcta? |

---

## ✅ Requisitos Encontrados ({len(found_reqs)})

| # | Tipo de Requisito | Puntuación | Estado |
|---|-------------------|------------|--------|
"""
    
    for e in found_reqs:
        score_emoji = "🟢" if e["overall_score"] >= 0.75 else "🟡" if e["overall_score"] >= 0.5 else "🔴"
        md += f"| {e['requirement_id']} | {e['requirement_type'][:50]} | {e['overall_score']:.0%} | {score_emoji} |\n"
    
    if not found_reqs:
        md += "| - | No se encontraron requisitos | - | - |\n"
    
    md += f"""
### Detalles

"""
    
    for e in found_reqs:
        score_emoji = "🟢" if e["overall_score"] >= 0.75 else "🟡" if e["overall_score"] >= 0.5 else "🔴"
        md += f"""<details>
<summary>{score_emoji} <b>#{e['requirement_id']}</b> - {e['requirement_type'][:60]}</summary>

- **Esperado:** {e['expected_output'][:150]}{'...' if len(e['expected_output']) > 150 else ''}
- **Encontrado en:** {e['matched_section'] if e['matched_section'] else 'Sección no especificada'}
- **Puntuación:** {e['overall_score']:.0%}
- **Evaluación:** {e['reasoning'][:200]}{'...' if len(e['reasoning']) > 200 else ''}

</details>

"""
    
    md += f"""---

## ❌ Requisitos Faltantes ({len(missed_reqs)})

"""
    
    if missed_reqs:
        md += """| # | Tipo de Requisito | Qué se esperaba |
|---|-------------------|-----------------|
"""
        for e in missed_reqs:
            expected = e['expected_output'][:80] + '...' if len(e['expected_output']) > 80 else e['expected_output']
            md += f"| {e['requirement_id']} | {e['requirement_type'][:40]} | {expected} |\n"
        
        md += """
### ⚠️ Acción Requerida
Verificar si estos requisitos aplican a esta licitación.

"""
    else:
        md += """✅ **¡Excelente!** Todos los requisitos fueron encontrados.

"""
    
    md += f"""---

## 📝 Notas Metodológicas

- **Modelo:** {report.evaluator_model}
- **Método:** LLM-as-Judge con documento completo (sin chunking)
- **Idiomas:** Español/Inglés (equivalencia semántica)

---

*Generado por Requirements Extraction Evaluator v2*
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"📄 User-friendly report saved to: {output_path}")


def save_report(report: EvaluationReport, output_path: str):
    """Save the evaluation report as JSON."""
    report_dict = {
        "summary": {
            "total_requirements": report.total_requirements,
            "requirements_found": report.requirements_found,
            "requirements_missed": report.requirements_missed,
            "avg_presence_score": sanitize_float(report.avg_presence_score),
            "avg_completeness_score": sanitize_float(report.avg_completeness_score),
            "avg_accuracy_score": sanitize_float(report.avg_accuracy_score),
            "avg_overall_score": sanitize_float(report.avg_overall_score),
        },
        "metadata": {
            "timestamp": report.evaluation_timestamp,
            "evaluator_model": report.evaluator_model,
            "ground_truth_path": report.ground_truth_path,
            "generated_path": report.generated_path,
            "evaluation_method": "LLM-as-Judge v2 (full document, no chunking)"
        },
        "evaluations": report.evaluations
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)


# =============================================================================
# MAIN
# =============================================================================
def main():
    """Main entry point."""
    print("\n🚀 Requirements Extraction Evaluator v2 - LLM-as-Judge")
    print("=" * 60)
    
    # Check boto3 is available first (needed for S3 operations)
    try:
        import boto3
    except ImportError:
        print("❌ boto3 required. Install: pip install boto3")
        sys.exit(1)
    
    # Generate run timestamp
    run_timestamp = get_run_timestamp()
    
    # Build S3 output prefix with timestamp
    s3_output_prefix = OUTPUT_S3_URI.rstrip("/") + "/" + run_timestamp + "/"
    
    print(f"\n📁 Run Timestamp: {run_timestamp}")
    print(f"   S3 Output: {s3_output_prefix}")
    
    # Check if input files exist
    print(f"\n📂 Checking input files...")
    print(f"   Ground Truth: {GROUND_TRUTH_CSV_PATH}")
    print(f"   Generated:    {GENERATED_REQUIREMENTS_PATH}")
    
    if not check_file_exists(GROUND_TRUTH_CSV_PATH):
        print(f"❌ Ground truth CSV not found: {GROUND_TRUTH_CSV_PATH}")
        sys.exit(1)
    print(f"   ✓ Ground truth file exists")
    
    if not check_file_exists(GENERATED_REQUIREMENTS_PATH):
        print(f"❌ Generated requirements not found: {GENERATED_REQUIREMENTS_PATH}")
        sys.exit(1)
    print(f"   ✓ Generated requirements file exists")
    
    # Copy input files to S3 output directory
    print(f"\n📋 Copying input files to S3 output directory...")
    s3_copied_files = copy_input_files_to_s3(s3_output_prefix, GROUND_TRUTH_CSV_PATH, GENERATED_REQUIREMENTS_PATH)
    
    print(f"\n📂 Loading ground truth from CSV...")
    requirements = read_ground_truth_csv(GROUND_TRUTH_CSV_PATH)
    print(f"   Loaded {len(requirements)} requirements")
    
    print(f"\n📂 Loading generated document...")
    generated_document = read_generated_requirements(GENERATED_REQUIREMENTS_PATH)
    print(f"   Loaded {len(generated_document):,} characters")
    
    print(f"\n🔍 Running LLM-as-Judge evaluation...")
    print(f"   Model: {EVALUATOR_LLM_MODEL}")
    print(f"   Method: Full document, single LLM call (boto3)")
    
    report = evaluate_all_requirements(requirements, generated_document)
    
    print_report(report)
    
    # Generate report content
    print(f"\n📤 Uploading reports to S3...")
    
    # Generate JSON report content
    report_dict = {
        "summary": {
            "total_requirements": report.total_requirements,
            "requirements_found": report.requirements_found,
            "requirements_missed": report.requirements_missed,
            "avg_presence_score": sanitize_float(report.avg_presence_score),
            "avg_completeness_score": sanitize_float(report.avg_completeness_score),
            "avg_accuracy_score": sanitize_float(report.avg_accuracy_score),
            "avg_overall_score": sanitize_float(report.avg_overall_score),
        },
        "metadata": {
            "timestamp": report.evaluation_timestamp,
            "run_timestamp": run_timestamp,
            "evaluator_model": report.evaluator_model,
            "ground_truth_path": report.ground_truth_path,
            "generated_path": report.generated_path,
            "s3_output_prefix": s3_output_prefix,
            "evaluation_method": "LLM-as-Judge v2 (full document, no chunking)"
        },
        "evaluations": report.evaluations
    }
    json_content = json.dumps(report_dict, indent=2, ensure_ascii=False)
    
    # Generate Markdown report content
    score = report.avg_overall_score
    if score >= 0.9:
        grade = "🏆 Excelente"
        grade_desc = "La extracción de requisitos es de alta calidad."
    elif score >= 0.75:
        grade = "✅ Bueno"
        grade_desc = "La mayoría de los requisitos fueron extraídos correctamente."
    elif score >= 0.6:
        grade = "⚠️ Aceptable"
        grade_desc = "Algunos requisitos necesitan revisión manual."
    elif score >= 0.4:
        grade = "🔶 Necesita Mejora"
        grade_desc = "Se recomienda revisión detallada del documento."
    else:
        grade = "❌ Insuficiente"
        grade_desc = "Requiere revisión completa y re-extracción."
    
    found_reqs = [e for e in report.evaluations if e["found"]]
    missed_reqs = [e for e in report.evaluations if not e["found"]]
    
    md_content = f"""# 📊 Informe de Evaluación de Requisitos

> **Fecha:** {datetime.now().strftime("%d/%m/%Y %H:%M")}  
> **Run Timestamp:** {run_timestamp}  
> **Documento Evaluado:** `{get_filename_from_path(report.generated_path)}`

---

## 🎯 Resumen Ejecutivo

| Métrica | Resultado |
|---------|-----------|
| **Calificación General** | {grade} |
| **Puntuación** | **{score:.0%}** |
| **Requisitos Encontrados** | {report.requirements_found} de {report.total_requirements} ({report.requirements_found/report.total_requirements*100:.0f}%) |
| **Requisitos Faltantes** | {report.requirements_missed} |

### Interpretación
{grade_desc}

---

## 📈 Puntuaciones por Categoría

| Categoría | Puntuación | Significado |
|-----------|------------|-------------|
| **Presencia** | {report.avg_presence_score:.0%} | ¿Se encontró el requisito en el documento? |
| **Completitud** | {report.avg_completeness_score:.0%} | ¿Están todos los detalles incluidos? |
| **Precisión** | {report.avg_accuracy_score:.0%} | ¿La información es correcta? |

---

## ✅ Requisitos Encontrados ({len(found_reqs)})

| # | Tipo de Requisito | Puntuación | Estado |
|---|-------------------|------------|--------|
"""
    
    for e in found_reqs:
        score_emoji = "🟢" if e["overall_score"] >= 0.75 else "🟡" if e["overall_score"] >= 0.5 else "🔴"
        md_content += f"| {e['requirement_id']} | {e['requirement_type'][:50]} | {e['overall_score']:.0%} | {score_emoji} |\n"
    
    if not found_reqs:
        md_content += "| - | No se encontraron requisitos | - | - |\n"
    
    md_content += f"""
### Detalles

"""
    
    for e in found_reqs:
        score_emoji = "🟢" if e["overall_score"] >= 0.75 else "🟡" if e["overall_score"] >= 0.5 else "🔴"
        md_content += f"""<details>
<summary>{score_emoji} <b>#{e['requirement_id']}</b> - {e['requirement_type'][:60]}</summary>

- **Esperado:** {e['expected_output'][:150]}{'...' if len(e['expected_output']) > 150 else ''}
- **Encontrado en:** {e['matched_section'] if e['matched_section'] else 'Sección no especificada'}
- **Puntuación:** {e['overall_score']:.0%}
- **Evaluación:** {e['reasoning'][:200]}{'...' if len(e['reasoning']) > 200 else ''}

</details>

"""
    
    md_content += f"""---

## ❌ Requisitos Faltantes ({len(missed_reqs)})

"""
    
    if missed_reqs:
        md_content += """| # | Tipo de Requisito | Qué se esperaba |
|---|-------------------|-----------------|
"""
        for e in missed_reqs:
            expected = e['expected_output'][:80] + '...' if len(e['expected_output']) > 80 else e['expected_output']
            md_content += f"| {e['requirement_id']} | {e['requirement_type'][:40]} | {expected} |\n"
        
        md_content += """
### ⚠️ Acción Requerida
Verificar si estos requisitos aplican a esta licitación.

"""
    else:
        md_content += """✅ **¡Excelente!** Todos los requisitos fueron encontrados.

"""
    
    md_content += f"""---

## 📝 Notas Metodológicas

- **Modelo:** {report.evaluator_model}
- **Método:** LLM-as-Judge con documento completo (sin chunking)
- **Idiomas:** Español/Inglés (equivalencia semántica)
- **S3 Output:** {s3_output_prefix}

---

*Generado por Requirements Extraction Evaluator v2*
"""
    
    # Upload reports to S3
    json_s3_uri = f"{s3_output_prefix}{OUTPUT_REPORT_JSON}"
    md_s3_uri = f"{s3_output_prefix}{OUTPUT_REPORT_MD}"
    
    upload_to_s3(json_content, json_s3_uri, "application/json")
    print(f"   ✓ Uploaded: {OUTPUT_REPORT_JSON}")
    
    upload_to_s3(md_content, md_s3_uri, "text/markdown")
    print(f"   ✓ Uploaded: {OUTPUT_REPORT_MD}")
    
    # Optionally save locally
    local_output_dir = None
    if SAVE_LOCALLY:
        print(f"\n💾 Saving reports locally...")
        local_output_dir = create_output_directory(run_timestamp)
        
        # Save reports locally
        local_json_path = os.path.join(local_output_dir, OUTPUT_REPORT_JSON)
        local_md_path = os.path.join(local_output_dir, OUTPUT_REPORT_MD)
        
        with open(local_json_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
        print(f"   ✓ Saved: {OUTPUT_REPORT_JSON}")
        
        with open(local_md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"   ✓ Saved: {OUTPUT_REPORT_MD}")
        
        # Copy input files locally
        local_copied_files = copy_input_files_to_output(local_output_dir, GROUND_TRUTH_CSV_PATH, GENERATED_REQUIREMENTS_PATH)
    
    # Print summary
    print(f"\n" + "=" * 60)
    print(f"📄 S3 Output Directory: {s3_output_prefix}")
    print(f"   ├── {OUTPUT_REPORT_JSON}")
    print(f"   ├── {OUTPUT_REPORT_MD}")
    if s3_copied_files.get("ground_truth"):
        print(f"   ├── {get_filename_from_path(s3_copied_files['ground_truth'])}")
    if s3_copied_files.get("generated"):
        print(f"   └── {get_filename_from_path(s3_copied_files['generated'])}")
    
    if SAVE_LOCALLY and local_output_dir:
        print(f"\n📂 Local Output Directory: {local_output_dir}")
        print(f"   ├── {OUTPUT_REPORT_JSON}")
        print(f"   ├── {OUTPUT_REPORT_MD}")
        if local_copied_files.get("ground_truth"):
            print(f"   ├── {os.path.basename(local_copied_files['ground_truth'])}")
        if local_copied_files.get("generated"):
            print(f"   └── {os.path.basename(local_copied_files['generated'])}")
    
    print("=" * 60)
    
    return report


if __name__ == "__main__":
    main()
