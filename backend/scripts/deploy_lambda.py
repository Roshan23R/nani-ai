"""Deploy the API to Lambda behind an HTTP API Gateway.

No Docker required: dependencies are fetched as Linux wheels with pip's
--platform flag and zipped alongside the app. Re-running updates in place.

    backend/venv/bin/python backend/scripts/deploy_lambda.py
    backend/venv/bin/python backend/scripts/deploy_lambda.py --skip-build

Why Lambda and not the App Runner container originally planned: Docker is not
installed on the build machine, and every handler already completes one bounded
state transition, so nothing approaches API Gateway's hard 29-second cut-off.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from tools.config import (  # noqa: E402
    GOOGLE_CALENDAR_ID,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_PLACES_API_KEY,
    GOOGLE_REFRESH_TOKEN,
    S3_BUCKET,
    SES_DOCTOR_RECIPIENT,
    SES_LAB_RECIPIENT,
    SES_SENDER,
)

REGION = "us-east-1"
FUNCTION = "nani-ai-api"
ROLE_NAME = "nani-ai-lambda-role"
API_NAME = "nani-ai-http"
RUNTIME = "python3.13"
ARCH = "x86_64"
BUILD = Path("/tmp/nani-lambda-build")
APP_DIRS = ["agents", "api", "state", "tools"]
APP_FILES = ["coordinator.py"]

# API Gateway's own CORS config answers the preflight and overrides whatever
# FastAPI's middleware would say, so PUT/PATCH must be listed here too or the
# profile save fails in the browser with no server-side error.
CORS = {
    "AllowOrigins": ["*"],
    "AllowMethods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "AllowHeaders": ["*"],
    "MaxAge": 600,
}

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": "arn:aws:logs:*:*:*",
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan",
            ],
            "Resource": f"arn:aws:dynamodb:{REGION}:*:table/nani-ai",
        },
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "Resource": [f"arn:aws:s3:::{S3_BUCKET}", f"arn:aws:s3:::{S3_BUCKET}/*"],
        },
        {"Effect": "Allow", "Action": ["ses:SendEmail", "ses:GetSendQuota"], "Resource": "*"},
        {
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            "Resource": "*",
        },
    ],
}


def build_zip(skip_build: bool) -> bytes:
    pkg = BUILD / "pkg"
    if not skip_build:
        BUILD.mkdir(parents=True, exist_ok=True)
        req = BUILD / "req.txt"
        lines = [
            l for l in (BACKEND / "requirements.txt").read_text().splitlines()
            if not l.lower().startswith(("boto3", "s3transfer", "pytest", "iniconfig", "pluggy"))
        ]
        req.write_text("\n".join(lines))
        print("  fetching Linux wheels ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--target", str(pkg),
             "--platform", "manylinux2014_x86_64", "--python-version", "3.13",
             "--only-binary=:all:", "--implementation", "cp", "-r", str(req)],
            check=True,
        )

    print("  zipping ...")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in pkg.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc"):
                z.write(path, path.relative_to(pkg))
        for d in APP_DIRS:
            for path in (BACKEND / d).rglob("*.py"):
                if "__pycache__" not in path.parts:
                    z.write(path, path.relative_to(BACKEND))
        for f in APP_FILES:
            z.write(BACKEND / f, f)
    data = buf.getvalue()
    print(f"  bundle: {len(data) / 1e6:.1f} MB zipped")
    return data


def ensure_role() -> str:
    iam = boto3.client("iam")
    try:
        arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        print(f"  role exists: {arn}")
    except ClientError:
        arn = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description="Nani AI API Lambda",
        )["Role"]["Arn"]
        print(f"  role created: {arn}")
        time.sleep(10)  # IAM is eventually consistent
    iam.put_role_policy(
        RoleName=ROLE_NAME, PolicyName="nani-ai-access", PolicyDocument=json.dumps(POLICY)
    )
    return arn


def env_vars() -> dict[str, str]:
    """AWS_REGION is reserved in Lambda — the runtime supplies it."""
    out = {
        "NANI_TABLE": "nani-ai",
        "S3_BUCKET": S3_BUCKET,
        "SES_SENDER": SES_SENDER,
        "SES_LAB_RECIPIENT": SES_LAB_RECIPIENT,
        "SES_DOCTOR_RECIPIENT": SES_DOCTOR_RECIPIENT,
        "GOOGLE_CALENDAR_ID": GOOGLE_CALENDAR_ID,
    }
    for k, v in {
        "GOOGLE_PLACES_API_KEY": GOOGLE_PLACES_API_KEY,
        "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": GOOGLE_REFRESH_TOKEN,
    }.items():
        if v:
            out[k] = v
    return out


def deploy_function(zip_bytes: bytes, role_arn: str) -> str:
    lam = boto3.client("lambda", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    key = "deploy/nani-ai-api.zip"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=zip_bytes)
    print(f"  uploaded to s3://{S3_BUCKET}/{key}")

    config = dict(
        Role=role_arn,
        Handler="api.main.handler",
        Runtime=RUNTIME,
        Timeout=120,
        MemorySize=1536,
        Environment={"Variables": env_vars()},
    )
    try:
        lam.get_function(FunctionName=FUNCTION)
        lam.update_function_code(FunctionName=FUNCTION, S3Bucket=S3_BUCKET, S3Key=key)
        _wait(lam)
        lam.update_function_configuration(FunctionName=FUNCTION, **config)
        print("  function updated")
    except lam.exceptions.ResourceNotFoundException:
        lam.create_function(
            FunctionName=FUNCTION,
            Code={"S3Bucket": S3_BUCKET, "S3Key": key},
            Architectures=[ARCH],
            **config,
        )
        print("  function created")
    _wait(lam)
    return lam.get_function(FunctionName=FUNCTION)["Configuration"]["FunctionArn"]


def _wait(lam) -> None:
    for _ in range(60):
        state = lam.get_function(FunctionName=FUNCTION)["Configuration"]
        if state.get("LastUpdateStatus") != "InProgress" and state.get("State") != "Pending":
            return
        time.sleep(2)


def ensure_api(function_arn: str) -> str:
    api = boto3.client("apigatewayv2", region_name=REGION)
    existing = next(
        (a for a in api.get_apis()["Items"] if a["Name"] == API_NAME), None
    )
    if existing:
        api_id, url = existing["ApiId"], existing["ApiEndpoint"]
        api.update_api(ApiId=api_id, CorsConfiguration=CORS)
        print(f"  api exists: {api_id} (cors refreshed)")
    else:
        created = api.create_api(
            Name=API_NAME,
            ProtocolType="HTTP",
            Target=function_arn,
            CorsConfiguration=CORS,
        )
        api_id, url = created["ApiId"], created["ApiEndpoint"]
        print(f"  api created: {api_id}")

    lam = boto3.client("lambda", region_name=REGION)
    account = boto3.client("sts").get_caller_identity()["Account"]
    try:
        lam.add_permission(
            FunctionName=FUNCTION,
            StatementId="apigw-invoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{account}:{api_id}/*/*",
        )
        print("  invoke permission added")
    except lam.exceptions.ResourceConflictException:
        pass
    return url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true", help="Reuse the wheels already fetched")
    args = ap.parse_args()

    print("building")
    zip_bytes = build_zip(args.skip_build)
    print("iam")
    role_arn = ensure_role()
    print("lambda")
    fn_arn = deploy_function(zip_bytes, role_arn)
    print("api gateway")
    url = ensure_api(fn_arn)

    print("\n" + "=" * 62)
    print(f"  API base URL   {url}")
    print(f"  health         {url}/api/health")
    print("=" * 62)
    print("\nFrontend needs a REBUILD, not a config change:")
    print(f"  NEXT_PUBLIC_API_BASE_URL={url}")
    print("  NEXT_PUBLIC_USE_MOCKS=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
