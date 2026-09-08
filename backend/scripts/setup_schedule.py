"""Point EventBridge Scheduler at the tick handler.

The heartbeat is the second trigger and the reason this is an agent rather than
a form: the patient starts an episode, and the scheduler carries it forward for
days without anyone opening the app.

    backend/venv/bin/python backend/scripts/setup_schedule.py
    backend/venv/bin/python backend/scripts/setup_schedule.py --rate "rate(5 minutes)"
"""

from __future__ import annotations

import argparse
import json
import time

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION = "nani-ai-api"
SCHEDULE = "nani-ai-heartbeat"
ROLE_NAME = "nani-ai-scheduler-role"
DEFAULT_RATE = "rate(2 minutes)"

TRUST = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "scheduler.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


def ensure_role(function_arn: str) -> str:
    iam = boto3.client("iam")
    try:
        arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
    except ClientError:
        arn = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST),
            Description="Lets EventBridge Scheduler invoke the Nani AI heartbeat",
        )["Role"]["Arn"]
        print(f"  role created: {arn}")
        time.sleep(10)
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="invoke-tick",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": function_arn}
                ],
            }
        ),
    )
    return arn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", default=DEFAULT_RATE,
                    help='EventBridge expression, e.g. "rate(5 minutes)"')
    args = ap.parse_args()

    lam = boto3.client("lambda", region_name=REGION)
    fn_arn = lam.get_function(FunctionName=FUNCTION)["Configuration"]["FunctionArn"]
    role_arn = ensure_role(fn_arn)

    sch = boto3.client("scheduler", region_name=REGION)
    params = dict(
        Name=SCHEDULE,
        ScheduleExpression=args.rate,
        FlexibleTimeWindow={"Mode": "OFF"},
        Target={
            "Arn": fn_arn,
            "RoleArn": role_arn,
            "Input": json.dumps({"nani_tick": True}),
            # The claim in state/idempotency.py is what makes a retry safe.
            "RetryPolicy": {"MaximumRetryAttempts": 2},
        },
        Description="Carries every live Nani AI episode forward",
        State="ENABLED",
    )
    try:
        sch.create_schedule(**params)
        print(f"  schedule created: {SCHEDULE}  {args.rate}")
    except sch.exceptions.ConflictException:
        sch.update_schedule(**params)
        print(f"  schedule updated: {SCHEDULE}  {args.rate}")

    got = sch.get_schedule(Name=SCHEDULE)
    print(f"  state       {got['State']}")
    print(f"  expression  {got['ScheduleExpression']}")
    print(f"  target      {got['Target']['Arn'].rsplit(':', 1)[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
