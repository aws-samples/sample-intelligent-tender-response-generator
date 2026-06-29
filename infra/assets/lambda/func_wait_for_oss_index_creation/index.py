import os
import time
import urllib3

from botocore.awsrequest import AWSRequest
from botocore.auth import SigV4Auth
from botocore.session import Session

http = urllib3.PoolManager()


def _normalize_endpoint(ep: str) -> str:
    ep = ep.strip()

    if ep.startswith("https://"):
        return ep

    if ep.startswith("http://"):
        raise ValueError("Use https")

    return f"https://{ep}"


def _sigv4(method: str, url: str, region: str, service: str = "aoss"):
    session = Session()
    creds = session.get_credentials().get_frozen_credentials()

    req = AWSRequest(method=method, url=url, data=None, headers={})
    SigV4Auth(creds, service, region).add_auth(req)
    headers = dict(req.headers.items())

    resp = http.request(method, url, headers=headers, preload_content=False)
    body = resp.data.decode("utf-8") if resp.data else ""

    return resp.status, body


def handler(event, context):
    req_type = event["RequestType"]
    props = event.get("ResourceProperties", {})

    endpoint = _normalize_endpoint(props["CollectionEndpoint"])
    index_name = props["IndexName"]

    if req_type == "Delete":
        return {"PhysicalResourceId": f"{endpoint}/{index_name}"}

    region = os.environ["AWS_REGION"]
    url = f"{endpoint}/{index_name}"

    while True:
        status, body = _sigv4("GET", url, region)
        print(status, body)

        if status in (200, 204) and index_name in body:
            time.sleep(60)

            return {
                "PhysicalResourceId": f"{endpoint}/{index_name}",
                "Data": {"Ready": "true", "IndexName": index_name},
            }
        else:
            print(f'Index {index_name} not found yet')

        time.sleep(10)
