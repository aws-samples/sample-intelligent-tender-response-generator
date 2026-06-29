# Front-end (React + Cloudscape)

The web client for the *Intelligent Tender Response Generator* — a
[Create React App](https://github.com/facebook/create-react-app) project using the
[Cloudscape Design System](https://cloudscape.design/). It lets a signed-in user upload
tender documents, start a response-generation workflow, and watch progress in real time
over a WebSocket.

> **You normally do not build or deploy this app yourself.** `cdk deploy --all` (see the
> [root README](../README.md)) zips this `front-end/` directory, seeds a CodeCommit
> repository with it, and **AWS Amplify** builds and hosts it — injecting the backend
> wiring as build-time environment variables. The sections below are for running the UI
> locally during development.

## Backend configuration (`REACT_APP_*`)

The app reads all backend wiring from build-time environment variables. In the deployed
environment Amplify sets these automatically (from the CDK `WebAppPattern` construct); for
local development you supply them via a `.env.local` file.

| Variable | Purpose |
| -------- | ------- |
| `REACT_APP_COGNITO_AUTHORITY` | Cognito issuer URL (OIDC). |
| `REACT_APP_USER_POOL_CLIENT_ID` | Cognito app client ID. |
| `REACT_APP_COGNITO_DOMAIN` | Cognito hosted-UI domain. |
| `REACT_APP_API_URL` | REST API base URL (`…/dev`). |
| `REACT_APP_WSS_URL` | WebSocket API URL for live progress updates. |
| `REACT_APP_API_KEY` | API Gateway usage/throttling key (delivered to the browser by design). |

## Run locally against the deployed backend

`http://localhost:3000` is already an allowed Cognito callback and the REST API allows all
CORS origins, so a locally served front-end can talk to the deployed backend with no extra
setup.

```bash
cp .env.example .env.local         # then fill in the six values above
npm install
npm start                          # opens http://localhost:3000
```

See **Local front-end development** in the [root README](../README.md) for the exact AWS
CLI commands that fetch each `REACT_APP_*` value from the deployed stack, and
[Create a login user](../README.md#create-a-login-user) for sign-in credentials.

## Preview the UI without a backend

To explore the interface with no deployed backend (no Cognito sign-in, no API calls), run
in preview mode:

```bash
REACT_APP_PREVIEW=true npm start
```

This substitutes a mock auth session and seeds the dropdown data from static fixtures
([`src/utils/previewData.js`](src/utils/previewData.js)) so pages render. API/WebSocket
calls are skipped, so tables and actions that need the backend will be empty or inert.
The flag is off by default and has no effect on a normal build or the deployed app.

## Notable behaviour

- **Authentication** — OIDC via `react-oidc-context`; the app is gated behind a Cognito
  sign-in (`src/utils/AuthGate.js`).
- **File uploads** — the input-files picker accepts **images, Word documents (.docx) and
  PDF** only. Both the file picker and drag-and-drop are validated client-side, and
  unsupported files are reported via a Cloudscape Flashbar
  (`src/reusable_components/file_upload/file_upload.js`).
- **Real-time updates** — workflow progress arrives over the WebSocket and updates the
  Zustand stores in `src/data_store/`.

## Available scripts

| Command | Description |
| ------- | ----------- |
| `npm start` | Run the dev server on `http://localhost:3000`. |
| `npm run build` | Production build into `build/` (Amplify runs this during its hosted build). |
| `npm test` | Run the test runner in watch mode. |

> `npm audit` reports advisories in CRA's **build-time** tooling (webpack, jest, eslint,
> etc.). These run only during `npm run build`/test and are **not** part of the shipped
> browser bundle. See the Security section of the [root README](../README.md).
