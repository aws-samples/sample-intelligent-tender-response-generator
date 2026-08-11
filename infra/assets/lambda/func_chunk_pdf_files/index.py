import json
import os
import re
import tempfile

from system_layer import *
from concurrent.futures import ThreadPoolExecutor, as_completed
from pypdf import PdfReader, PdfWriter
from boto3.s3.transfer import TransferConfig

s3 = get_client("s3")

MAX_PAGES = int(os.environ.get("MAX_PAGES", "100"))
OVERLAP = min(float(os.environ.get("PAGE_OVERLAP", "0.1")), 0.3)
SRC_BUCKET = os.environ.get("SRC_BUCKET")
DST_BUCKET = os.environ.get("DST_BUCKET")
CHUNK_SUFFIX_RE = re.compile(r"_\d+\.pdf$", re.IGNORECASE)
INDEXED_FILES_PREFIX = 'to_index'


# ==================== S3 OPERATIONS ==================== #
def list_pdfs(bucket: str, start_prefix):
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=start_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # Avoid re-splitting already-generated chunks
            if not key.lower().endswith(".pdf") or CHUNK_SUFFIX_RE.search(key):
                continue

            yield key


def retrieve_file_tags(key, bucket):
    tags = s3.get_object_tagging(Bucket=bucket, Key=key).get("TagSet", [])
    category = None
    pages = None

    for tag in tags:
        if tag["Key"] == TAG_PAGE_COUNT:
            pages = int(tag["Value"])
        elif tag["Key"] == TAG_CATEGORY:
            category = tag["Value"]

    return None if category is None or pages is None else {'Category': category, 'PageCount': pages}


def upload_file(local_path, dst_bucket, dst_key, **kwargs):
    return s3.upload_file(local_path, dst_bucket, dst_key, **kwargs)


def copy_file(key, dst_key, src_bucket, dst_bucket):
    s3.copy_object(
        Bucket=dst_bucket,
        Key=dst_key,
        CopySource={
            "Bucket": src_bucket,
            "Key": key
        }
    )
# ======================================================= #


# ================== CHUNKING HELPERS =================== #
def split_pdf_local(src_path: str, max_pages: int, total_pages: int, page_overlap: int) -> list:
    reader = PdfReader(src_path)
    chunks = []
    chunk_index = 1

    for start in range(0, total_pages, max_pages):
        first_page = max(0, start - page_overlap)
        last_page = min(start + max_pages + page_overlap, total_pages)

        writer = PdfWriter()

        for i in range(first_page, last_page):
            writer.add_page(reader.pages[i])

        fd, out_path = tempfile.mkstemp(prefix=f"chunk_{chunk_index}_", suffix=".pdf")

        with os.fdopen(fd, "wb") as f:
            writer.write(f)

        chunks.append((chunk_index, out_path))
        chunk_index += 1

    return chunks


def build_chunk_key(original_key: str, chunk_index: int) -> str:
    # Preserve original prefix (folders) and base filename
    if "/" in original_key:
        prefix, filename = original_key.rsplit("/", 1)
        base = filename[:-4]
        return f"{prefix}/{base}_{chunk_index}.pdf"
    else:
        base = original_key[:-4]
        return f"{base}_{chunk_index}.pdf"


def parallel_upload_chunks(original_key, chunks, dst_bucket):
    cfg = TransferConfig(max_concurrency=10)
    dst_keys = []

    with ThreadPoolExecutor(max_workers=min(16, len(chunks))) as ex:
        jobs = []

        for chunk_index, local_chunk_path in chunks:
            dst_key = build_chunk_key(original_key, chunk_index)
            dst_keys.append(dst_key)

            jobs.append(
                ex.submit(
                    upload_file,local_chunk_path, dst_bucket, dst_key,
                    **{'Config': cfg, 'ExtraArgs': {"ContentType": "application/pdf"}}
                )
            )

        for j in as_completed(jobs):
            j.result()

    return dst_keys


def chunk_file(src_key, dst_key, src_bucket, dst_bucket, total_pages, page_overlap):
    fd, local_src = tempfile.mkstemp(prefix="source_", suffix=".pdf")
    os.close(fd)

    # Download object to a temporary file
    s3.download_file(src_bucket, src_key, local_src)
    chunks = split_pdf_local(local_src, MAX_PAGES, total_pages, page_overlap)

    # Upload chunks and return created chunk keys
    return parallel_upload_chunks(dst_key, chunks, dst_bucket)
# ======================================================= #


# ================== METADATA HELPERS =================== #
def generate_metadata(key, category, dst_bucket, prefix='metadata.json'):
    dst_key = f'{key}.{prefix}'

    metadata = {
        "metadataAttributes": {
            "category": category,
        }
    }

    fd, local_path = tempfile.mkstemp(suffix=f'.{prefix}')

    with os.fdopen(fd, 'w') as f:
        f.write(json.dumps(metadata))

    upload_file(local_path, dst_bucket, dst_key)
# ======================================================= #


# ================== GENERIC HELPERS ===================+ #
def needs_upload_file_to_indexed_path(category: str):
    return 'response' not in category.lower()


def add_indexed_path_to_key(key: str):
    key = key.split('/')
    key.insert(1, INDEXED_FILES_PREFIX)

    return '/'.join(key)
# ======================================================= #


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event["analysisId"]
    page_overlap = int(MAX_PAGES * OVERLAP // 2)

    # List the files in the staging bucket
    files = {
        key: {}
        for key in list_pdfs(SRC_BUCKET, f'{analysis_id}/')
    }

    # Retrieve file tags (file category and page count)
    for key in files:
        tags = retrieve_file_tags(key, SRC_BUCKET)

        if tags is None:
            del files[key]
        else:
            files[key] = tags

    # For each tagged file, either chunk it or copy it directly
    for key, tags in files.items():
        dst_key = key
        upload_to_indexed = needs_upload_file_to_indexed_path(tags['Category'])

        if upload_to_indexed:
            dst_key = add_indexed_path_to_key(dst_key)

        # Chunk the file
        if tags['PageCount'] > MAX_PAGES:
            chunk_keys = chunk_file(key, dst_key, SRC_BUCKET, DST_BUCKET, tags['PageCount'], page_overlap)

            if upload_to_indexed:
                for chunk_key in chunk_keys:
                    generate_metadata(chunk_key, tags['Category'], DST_BUCKET)
        # Copy the file directly
        else:
            copy_file(key, dst_key, SRC_BUCKET, DST_BUCKET)

            if upload_to_indexed:
                generate_metadata(dst_key, tags['Category'], DST_BUCKET)

    return {'statusCode': 200}
