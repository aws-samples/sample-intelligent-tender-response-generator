import os
import jwt
from jwt import PyJWKClient


USER_POOL_ID = os.environ["USER_POOL_ID"]
CLIENT_ID = os.environ["USER_POOL_CLIENT_ID"]
AWS_REGION = os.environ["AWS_REGION"]

ISS = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{ISS}/.well-known/jwks.json"
_jwks = PyJWKClient(JWKS_URL)


def _deny():
    return {
        "principalId": "unauthorized",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": "Deny", "Resource": "*"}],
        },
        "context": {},
    }


def _allow(pid: str, resource: str, ctx: dict):
    return {
        "principalId": pid,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": resource}],
        },
        "context": ctx,
    }


def handler(event, _ctx):
    token = event.get("queryStringParameters", {}).get("token")

    if not token:
        return _deny()

    try:
        key = _jwks.get_signing_key_from_jwt(token).key

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISS,
            options={"verify_aud": False, "verify_exp": True, "verify_iss": True},
        )

        tuse = claims.get("token_use")

        if tuse == "id":
            if claims.get("aud") != CLIENT_ID:
                return _deny()
        elif tuse == "access":
            if claims.get("client_id") != CLIENT_ID:
                return _deny()
        else:
            return _deny()

        user_id = claims.get("sub")
        username = claims.get("cognito:username") or claims.get("username") or user_id

        return _allow(
            pid=user_id,
            resource='*',
            ctx={"sub": user_id, "username": username, "token_use": tuse},
        )
    except Exception as e:
        print(e)
        return _deny()
