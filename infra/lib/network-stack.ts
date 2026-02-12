import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class NetworkStack extends cdk.Stack {
    /** 他スタックから参照する VPC */
    public readonly vpc: ec2.Vpc;

    /** API Lambda 用セキュリティグループ — Outbound: 443 (HTTPS) */
    public readonly sgLambda: ec2.SecurityGroup;

    /** バッチ Lambda 用セキュリティグループ — Outbound: 443 (HTTPS) */
    public readonly sgBatch: ec2.SecurityGroup;

    /** RDS 用セキュリティグループ — Inbound: 5432 from sg-lambda, sg-batch のみ */
    public readonly sgRds: ec2.SecurityGroup;

    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // =========================================================================
        // VPC — 10.0.0.0/16, 2 AZ 構成
        // =========================================================================
        this.vpc = new ec2.Vpc(this, 'AiResearchVpc', {
            ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
            maxAzs: 2,
            subnetConfiguration: [
                {
                    cidrMask: 24,
                    name: 'Public',
                    subnetType: ec2.SubnetType.PUBLIC,
                },
                {
                    cidrMask: 24,
                    name: 'Private',
                    subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
                },
            ],
            // コスト対策: 開発環境では NAT Gateway を 1 つに制限 (~$32/月)
            natGateways: 1,
        });

        // =========================================================================
        // セキュリティグループ
        // =========================================================================

        // --- sg-lambda: API Lambda 用 ---
        this.sgLambda = new ec2.SecurityGroup(this, 'SgLambda', {
            vpc: this.vpc,
            description: 'Security group for API Lambda functions',
            allowAllOutbound: false,
        });
        // Outbound: HTTPS (443) — 外部 API / AWS サービス呼び出し用
        this.sgLambda.addEgressRule(
            ec2.Peer.anyIpv4(),
            ec2.Port.tcp(443),
            'Allow HTTPS outbound',
        );

        // --- sg-batch: バッチ Lambda 用 ---
        this.sgBatch = new ec2.SecurityGroup(this, 'SgBatch', {
            vpc: this.vpc,
            description: 'Security group for Batch Lambda functions',
            allowAllOutbound: false,
        });
        // Outbound: HTTPS (443) — arXiv API / OpenAI / Gemini 呼び出し用
        this.sgBatch.addEgressRule(
            ec2.Peer.anyIpv4(),
            ec2.Port.tcp(443),
            'Allow HTTPS outbound',
        );

        // --- sg-rds: RDS PostgreSQL 用 ---
        this.sgRds = new ec2.SecurityGroup(this, 'SgRds', {
            vpc: this.vpc,
            description: 'Security group for RDS PostgreSQL',
            allowAllOutbound: false,
        });

        // Inbound: PostgreSQL (5432) — Lambda / Batch からのみ許可
        this.sgRds.addIngressRule(
            this.sgLambda,
            ec2.Port.tcp(5432),
            'Allow PostgreSQL from API Lambda',
        );
        this.sgRds.addIngressRule(
            this.sgBatch,
            ec2.Port.tcp(5432),
            'Allow PostgreSQL from Batch Lambda',
        );

        // Lambda / Batch から RDS への Outbound (5432) も許可
        this.sgLambda.addEgressRule(
            this.sgRds,
            ec2.Port.tcp(5432),
            'Allow PostgreSQL to RDS',
        );
        this.sgBatch.addEgressRule(
            this.sgRds,
            ec2.Port.tcp(5432),
            'Allow PostgreSQL to RDS',
        );

        // =========================================================================
        // CloudFormation Outputs — 他スタック参照 & コンソール確認用
        // =========================================================================
        new cdk.CfnOutput(this, 'VpcId', {
            value: this.vpc.vpcId,
            description: 'VPC ID',
            exportName: 'AiResearch-VpcId',
        });

        new cdk.CfnOutput(this, 'SgLambdaId', {
            value: this.sgLambda.securityGroupId,
            description: 'Lambda Security Group ID',
            exportName: 'AiResearch-SgLambdaId',
        });

        new cdk.CfnOutput(this, 'SgBatchId', {
            value: this.sgBatch.securityGroupId,
            description: 'Batch Security Group ID',
            exportName: 'AiResearch-SgBatchId',
        });

        new cdk.CfnOutput(this, 'SgRdsId', {
            value: this.sgRds.securityGroupId,
            description: 'RDS Security Group ID',
            exportName: 'AiResearch-SgRdsId',
        });
    }
}
