from constants import *


def get_object_bytes(s3, bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def set_object_tags(s3, bucket: str, object):
    tag_set = [
        {"Key": TAG_CATEGORY, "Value": object['Category']},
        {"Key": TAG_LAST_CLASSIFICATION_ETAG, "Value": object['ETag']},
        {"Key": TAG_SKIP_CLASSIFICATION, "Value": '0'},
        {"Key": TAG_PAGE_COUNT, "Value": object['PageCount']},
    ]

    s3.put_object_tagging(
        Bucket=bucket,
        Key=object['Key'],
        Tagging={"TagSet": tag_set}
    )


def list_prefix(s3, bucket, prefix):
    files = []

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            size = obj.get("Size", 0)
            etag = obj["ETag"].strip('"')

            category = ''
            last_classification_etag = ''
            page_count = '0'
            skip_classification = False

            # Folder marker
            if key.endswith("/") and size == 0:
                continue

            # Unsupported
            if not key.endswith('.pdf'):
                continue

            tagset = s3.get_object_tagging(Bucket=bucket, Key=key).get("TagSet", [])

            for tag in tagset:
                tag_key = tag["Key"]
                value = tag["Value"]

                if tag_key == TAG_SKIP_CLASSIFICATION and value == '1':
                    skip_classification = True
                elif tag_key == TAG_CATEGORY:
                    category = value
                elif tag_key == TAG_LAST_CLASSIFICATION_ETAG:
                    last_classification_etag = value
                elif tag_key == TAG_PAGE_COUNT:
                    page_count = value

            files.append({
                'Key': key,
                'ETag': etag,
                'SkipClassification': skip_classification or last_classification_etag == etag,
                'SkipPageCount': last_classification_etag == etag,
                'PageCount': page_count,
                'Category': category,
            })

    return files


def copy_object_preserving_tags(s3, src_bucket, dst_bucket, key):
    s3.copy_object(
        Bucket=dst_bucket,
        Key=key,
        CopySource={"Bucket": src_bucket, "Key": key},
        MetadataDirective="COPY",
        TaggingDirective="COPY",
    )
