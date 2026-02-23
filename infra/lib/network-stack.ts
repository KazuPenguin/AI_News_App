import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export class NetworkStack extends cdk.Stack {
  /** 他スタックから参照する VPC */
  public readonly vpc: ec2.Vpc;

  /** API Lambda 用セキュリティグループ — Outbound: 443 (HTTPS) */
  public readonly sgLambda: ec2.SecurityGroup;

  /** バッチ Lambda 用セキュリティグループ — Outbound: 443 (HTTPS) */
  public readonly sgBatch: ec2.SecurityGroup;

  /** RDS 用セキュリティグループ — Inbound: 5432 from sg-lambda, sg-batch, bastion のみ */
  public readonly sgRds: ec2.SecurityGroup;

  /** SSM 経由で DB にアクセスするための踏み台（Bastion Host） */
  public readonly bastion: ec2.BastionHostLinux;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================================
    // VPC — 10.0.0.0/16, 2 AZ 構成
    // =========================================================================

    // コスト対策: NAT Gateway (~$32/月) → t4g.nano NAT Instance (~$3/月)
    const natProvider = ec2.NatProvider.instanceV2({
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.NANO),
      defaultAllowedTraffic: ec2.NatTrafficDirection.OUTBOUND_ONLY,
    });

    this.vpc = new ec2.Vpc(this, "AiResearchVpc", {
      ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/16"),
      maxAzs: 2,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
      natGateways: 1,
      natGatewayProvider: natProvider,
    });

    // NAT Instance の SG に VPC 内 (Private Subnet) からの通信を許可
    natProvider.connections.allowFrom(
      ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
      ec2.Port.allTraffic(),
      "Allow traffic from private subnets",
    );

    // =========================================================================
    // 踏み台 (Bastion Host) — ローカルからの DB マイグレーション/シード用
    // =========================================================================
    this.bastion = new ec2.BastionHostLinux(this, "DbBastionHost", {
      vpc: this.vpc,
      subnetSelection: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T4G,
        ec2.InstanceSize.NANO,
      ),
    });

    // =========================================================================
    // セキュリティグループ
    // =========================================================================

    // --- sg-lambda: API Lambda 用 ---
    this.sgLambda = new ec2.SecurityGroup(this, "SgLambda", {
      vpc: this.vpc,
      description: "Security group for API Lambda functions",
      allowAllOutbound: false,
    });
    // Outbound: HTTPS (443) — 外部 API / AWS サービス呼び出し用
    this.sgLambda.addEgressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      "Allow HTTPS outbound",
    );

    // --- sg-batch: バッチ Lambda 用 ---
    this.sgBatch = new ec2.SecurityGroup(this, "SgBatch", {
      vpc: this.vpc,
      description: "Security group for Batch Lambda functions",
      allowAllOutbound: false,
    });
    // Outbound: HTTPS (443) — arXiv API / OpenAI / Gemini 呼び出し用
    this.sgBatch.addEgressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      "Allow HTTPS outbound",
    );

    // --- sg-rds: RDS PostgreSQL 用 ---
    this.sgRds = new ec2.SecurityGroup(this, "SgRds", {
      vpc: this.vpc,
      description: "Security group for RDS PostgreSQL",
      allowAllOutbound: false,
    });

    // Inbound: PostgreSQL (5432) — Lambda / Batch / Bastion からのみ許可
    this.sgRds.addIngressRule(
      this.sgLambda,
      ec2.Port.tcp(5432),
      "Allow PostgreSQL from API Lambda",
    );
    this.sgRds.addIngressRule(
      this.sgBatch,
      ec2.Port.tcp(5432),
      "Allow PostgreSQL from Batch Lambda",
    );
    this.sgRds.addIngressRule(
      this.bastion.connections.securityGroups[0],
      ec2.Port.tcp(5432),
      "Allow PostgreSQL from Bastion Host",
    );

    // Lambda / Batch から RDS への Outbound (5432) も許可
    this.sgLambda.addEgressRule(
      this.sgRds,
      ec2.Port.tcp(5432),
      "Allow PostgreSQL to RDS",
    );
    this.sgBatch.addEgressRule(
      this.sgRds,
      ec2.Port.tcp(5432),
      "Allow PostgreSQL to RDS",
    );

    // =========================================================================
    // CloudFormation Outputs — 他スタック参照 & コンソール確認用
    // =========================================================================
    new cdk.CfnOutput(this, "VpcId", {
      value: this.vpc.vpcId,
      description: "VPC ID",
      exportName: "AiResearch-VpcId",
    });

    new cdk.CfnOutput(this, "SgLambdaId", {
      value: this.sgLambda.securityGroupId,
      description: "Lambda Security Group ID",
      exportName: "AiResearch-SgLambdaId",
    });

    new cdk.CfnOutput(this, "SgBatchId", {
      value: this.sgBatch.securityGroupId,
      description: "Batch Security Group ID",
      exportName: "AiResearch-SgBatchId",
    });

    new cdk.CfnOutput(this, "SgRdsId", {
      value: this.sgRds.securityGroupId,
      description: "RDS Security Group ID",
      exportName: "AiResearch-SgRdsId",
    });

    new cdk.CfnOutput(this, "BastionInstanceId", {
      value: this.bastion.instanceId,
      description: "Bastion Host EC2 Instance ID",
      exportName: "AiResearch-BastionInstanceId",
    });
  }
}
