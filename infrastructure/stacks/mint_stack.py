from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_rds as rds,
    aws_elasticache as elasticache,
    aws_s3 as s3,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_secretsmanager as sm,
    aws_iam as iam,
)
from constructs import Construct


class MintStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ── VPC ──────────────────────────────────────────────────────────────
        vpc = ec2.Vpc(self, "MintVpc", max_azs=2, nat_gateways=1)

        # ── Security Groups ───────────────────────────────────────────────────
        db_sg = ec2.SecurityGroup(self, "DbSg", vpc=vpc, description="RDS PostgreSQL")
        redis_sg = ec2.SecurityGroup(self, "RedisSg", vpc=vpc, description="ElastiCache Redis")
        ecs_sg = ec2.SecurityGroup(self, "EcsSg", vpc=vpc, description="ECS tasks")

        db_sg.add_ingress_rule(ecs_sg, ec2.Port.tcp(5432))
        redis_sg.add_ingress_rule(ecs_sg, ec2.Port.tcp(6379))

        # ── RDS PostgreSQL ────────────────────────────────────────────────────
        db_secret = sm.Secret(self, "DbSecret",
            generate_secret_string=sm.SecretStringGenerator(
                secret_string_template='{"username":"mint_user"}',
                generate_string_key="password",
                exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/@\"\\",
            ),
        )

        db = rds.DatabaseInstance(self, "MintDb",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[db_sg],
            credentials=rds.Credentials.from_secret(db_secret),
            database_name="mint_db",
            removal_policy=RemovalPolicy.SNAPSHOT,
            deletion_protection=True,
            storage_encrypted=True,
        )

        # ── ElastiCache Redis ─────────────────────────────────────────────────
        redis_subnet_group = elasticache.CfnSubnetGroup(self, "RedisSubnetGroup",
            description="Redis subnet group",
            subnet_ids=[s.subnet_id for s in vpc.private_subnets],
        )

        redis = elasticache.CfnReplicationGroup(self, "MintRedis",
            replication_group_description="Mint Redis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            engine_version="7.1",
            num_cache_clusters=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            security_group_ids=[redis_sg.security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
        )

        # ── ECR Repositories ──────────────────────────────────────────────────
        backend_repo = ecr.Repository(self, "BackendRepo",
            repository_name="mint-backend",
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=10)],
        )

        # ── ECS Cluster ───────────────────────────────────────────────────────
        cluster = ecs.Cluster(self, "MintCluster", cluster_name="mint-cluster", vpc=vpc)

        # Task execution role
        exec_role = iam.Role(self, "TaskExecRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")],
        )
        db_secret.grant_read(exec_role)

        def db_url_from_secret():
            return f"postgresql://{{{{resolve:secretsmanager:{db_secret.secret_arn}:SecretString:username}}}}:{{{{resolve:secretsmanager:{db_secret.secret_arn}:SecretString:password}}}}@{db.db_instance_endpoint_address}:5432/mint_db"

        common_env = {
            "ENVIRONMENT": "production",
            "BACKEND_CORS_ORIGINS": '["https://yourdomain.com"]',
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        }

        # ── Backend Service ───────────────────────────────────────────────────
        backend_task = ecs.FargateTaskDefinition(self, "BackendTask",
            cpu=512, memory_limit_mib=1024,
            execution_role=exec_role,
        )
        backend_task.add_container("backend",
            image=ecs.ContainerImage.from_ecr_repository(backend_repo, "latest"),
            environment={
                **common_env,
                "REDIS_URL": f"rediss://{redis.attr_primary_end_point_address}:{redis.attr_primary_end_point_port}/0",
            },
            secrets={
                "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret, "password"),
                "SECRET_KEY": ecs.Secret.from_secrets_manager(
                    sm.Secret(self, "AppSecret", generate_secret_string=sm.SecretStringGenerator(password_length=64))
                ),
            },
            port_mappings=[ecs.PortMapping(container_port=8000)],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="mint-backend"),
        )

        backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(self, "BackendService",
            cluster=cluster,
            service_name="mint-backend-service",
            task_definition=backend_task,
            desired_count=2,
            security_groups=[ecs_sg],
            assign_public_ip=False,
            listener_port=443,
            health_check_grace_period=Duration.seconds(60),
        )
        backend_service.target_group.configure_health_check(path="/health")

        # ── Celery Worker ─────────────────────────────────────────────────────
        worker_task = ecs.FargateTaskDefinition(self, "WorkerTask",
            cpu=256, memory_limit_mib=512,
            execution_role=exec_role,
        )
        worker_task.add_container("worker",
            image=ecs.ContainerImage.from_ecr_repository(backend_repo, "latest"),
            environment={
                **common_env,
                "REDIS_URL": f"rediss://{redis.attr_primary_end_point_address}:{redis.attr_primary_end_point_port}/0",
            },
            command=["celery", "-A", "app.core.celery_app", "worker", "--loglevel=info", "-Q", "sync"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="mint-worker"),
        )
        ecs.FargateService(self, "WorkerService",
            cluster=cluster,
            service_name="mint-worker-service",
            task_definition=worker_task,
            desired_count=1,
            security_groups=[ecs_sg],
            assign_public_ip=False,
        )

        # ── S3 + CloudFront (Frontend) ────────────────────────────────────────
        frontend_bucket = s3.Bucket(self, "FrontendBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        oac = cf.S3OriginAccessControl(self, "OAC")
        distribution = cf.Distribution(self, "FrontendCDN",
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(frontend_bucket, origin_access_control=oac),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/api/*": cf.BehaviorOptions(
                    origin=origins.LoadBalancerV2Origin(backend_service.load_balancer),
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER,
                ),
            },
            error_responses=[
                cf.ErrorResponse(http_status=404, response_page_path="/index.html", response_http_status=200),
                cf.ErrorResponse(http_status=403, response_page_path="/index.html", response_http_status=200),
            ],
            default_root_object="index.html",
        )
