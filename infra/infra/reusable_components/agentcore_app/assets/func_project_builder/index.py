import boto3
import json
import logging
import time
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()
codebuild = boto3.client("codebuild")


class cfnresponse:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

    @staticmethod
    def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False, reason=None):
        responseUrl = event["ResponseURL"]

        responseBody = {
            "Status": responseStatus,
            "Reason": reason or f"See the details in CloudWatch Log Stream: {context.log_stream_name}",
            "PhysicalResourceId": physicalResourceId or event.get("PhysicalResourceId") or context.log_stream_name,
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
            "NoEcho": noEcho,
            "Data": responseData,
        }

        body = json.dumps(responseBody)
        headers = {"content-type": "", "content-length": str(len(body))}
        http.request("PUT", responseUrl, headers=headers, body=body)


def handler(event, context):
    logger.info("Received event: %s", json.dumps(event))
    req_type = event["RequestType"]

    props = event.get("ResourceProperties", {})
    project_name = props.get("ProjectName")
    source_hash = props.get("SourceHash", "nohash")
    physical_id = f"codebuild-trigger:{project_name}:{source_hash}"

    try:
        if req_type == "Delete":
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, physicalResourceId=physical_id)
            return

        # Start build
        resp = codebuild.start_build(projectName=project_name)
        build_id = resp["build"]["id"]
        logger.info("Started build: %s", build_id)

        # Wait for completion
        deadline = time.time() + (context.get_remaining_time_in_millis() / 1000.0) - 10
        sleep_s = 5

        while True:
            if time.time() > deadline:
                cfnresponse.send(
                    event, context, cfnresponse.FAILED,
                    {"Error": "Build timeout", "BuildId": build_id},
                    physicalResourceId=physical_id,
                )

                return

            br = codebuild.batch_get_builds(ids=[build_id])
            builds = br.get("builds", [])

            if not builds:
                time.sleep(sleep_s)
                continue

            status = builds[0].get("buildStatus")
            logger.info("Build %s status: %s", build_id, status)

            if status == "SUCCEEDED":
                cfnresponse.send(
                    event, context, cfnresponse.SUCCESS,
                    {"BuildId": build_id, "Status": status},
                    physicalResourceId=physical_id,
                )

                return

            if status in ("FAILED", "FAULT", "STOPPED", "TIMED_OUT"):
                cfnresponse.send(
                    event, context, cfnresponse.FAILED,
                    {"Error": f"Build failed: {status}", "BuildId": build_id},
                    physicalResourceId=physical_id,
                )

                return

            # light backoff up to 15s
            time.sleep(sleep_s)
            sleep_s = min(15, sleep_s + 2)

    except Exception as e:
        logger.exception("Error")

        cfnresponse.send(
            event, context, cfnresponse.FAILED,
            {"Error": str(e)},
            physicalResourceId=physical_id,
        )
