#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.mint_stack import MintStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or "123456789012",
    region=app.node.try_get_context("region") or "us-east-1",
)

MintStack(app, "MintStack", env=env, description="Mint personal finance app — ECS/RDS/Redis/CloudFront")

app.synth()
