# Infrastructure (AWS CDK — Python)

This directory holds the **AWS CDK (Python)** application for the *Intelligent Tender
Response Generator*. It defines the entire solution — the backend **and** the front-end
hosting — as four CDK stacks, and deploys with a single `cdk deploy --all`.

> For the full picture (architecture diagram, end-to-end deploy walkthrough, creating a
> login user, cost, and clean-up), see the [root README](../README.md). This file is a
> quick reference for working inside the `infra/` package.

## Stacks

The app entry point is [`app.py`](app.py); stack names and model IDs/ARNs come from
[`project_config.json`](project_config.json).

| Stack | Responsibility |
| ----- | -------------- |
| **CoreStack** | S3 buckets (raw / staging / clean / output / historic / multimodal), IAM roles, and the OpenSearch Serverless collection used by Bedrock Knowledge Bases. |
| **AgentCoreStack** | Two Amazon Bedrock AgentCore runtimes — a **Document Classifier** and a multi-agent **Response Generator** — built as container images via CodeBuild/ECR. |
| **FrontEndStack** | Cognito user pool, REST API + WebSocket API, API key/usage plan, AWS WAF, a CodeCommit repo seeded with the React source, and the AWS Amplify app that builds and hosts it. |
| **InfraStack** | The Lambda functions, the `AnalysisTable` DynamoDB table, and the durable orchestrator that run the analysis workflow, plus the API Gateway resource/method wiring. |

## Layout

```text
infra/
├── app.py                  CDK app entry point (instantiates the four stacks)
├── project_config.json     Stack names, model IDs/ARNs (and a re-enable-ready VPC block)
├── requirements.txt        Python dependencies for the CDK app
├── cdk.json                CDK Toolkit configuration
├── infra/                  Stack definitions + reusable CDK constructs
│   ├── core_stack.py
│   ├── agentcore_stack.py
│   ├── frontend_stack.py
│   ├── infra_stack.py
│   ├── knowledge_base_stack.py
│   └── reusable_components/ web_app, web_socket, agentcore_app, waf
└── assets/                 Lambda function code and AgentCore agent code
```

## Prerequisites

- AWS CLI v2, configured with credentials that can deploy these resources.
- Python 3.12+ and `pip` (deployed Lambda/AgentCore runtimes target Python 3.14; Docker
  handles their bundling).
- AWS CDK v2 (`npm install -g aws-cdk`).
- Docker running locally — CDK bundles the Python Lambda layers/functions and builds the
  AgentCore container images.
- **Amazon Bedrock model access** enabled in your target region for the Claude and Amazon
  Nova models referenced in [`project_config.json`](project_config.json) and
  [`infra/agentcore_stack.py`](infra/agentcore_stack.py). Defaults to **us-east-1**.

## Set up and deploy

```bash
# From this infra/ directory
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt

cdk bootstrap                      # once per account/region
cdk deploy --all                   # deploys backend + front-end together
```

You do **not** build the front-end yourself: CDK zips the `../front-end` source, seeds a
CodeCommit repository with it, and AWS Amplify builds and hosts the app. After the first
deploy, kick off the initial Amplify build and add the Amplify domain to Cognito — see the
[root README](../README.md) for those one-time steps, creating a login user, and clean-up.

## Useful commands

| Command | Description |
| ------- | ----------- |
| `cdk ls` | List the stacks in the app. |
| `cdk synth --all` | Synthesize the CloudFormation templates (also validates the code). |
| `cdk diff` | Compare a deployed stack with the current code. |
| `cdk deploy --all` | Deploy all four stacks. |
| `cdk destroy --all` | Tear everything down (see clean-up notes in the root README). |

To add a dependency, add it to [`requirements.txt`](requirements.txt) and re-run
`pip install -r requirements.txt`.
