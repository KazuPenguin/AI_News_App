import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

/**
 * BatchStack に渡す Props
 * NetworkStack, DatabaseStack, StorageStack からの参照を受け取る
 */
export interface BatchStackProps extends cdk.StackProps {
    /** NetworkStack の VPC */
    readonly vpc: ec2.IVpc;
    /** バッチ Lambda 用セキュリティグループ */
    readonly sgBatch: ec2.ISecurityGroup;
    /** RDS 接続用シークレット */
    readonly dbSecret: secretsmanager.ISecret;
    /** 論文図表保管用 S3 バケット */
    readonly figureBucket: s3.IBucket;
}

export class BatchStack extends cdk.Stack {
    /** バッチ処理 Lambda 関数 */
    public readonly batchHandler: lambda.DockerImageFunction;

    constructor(scope: Construct, id: string, props: BatchStackProps) {
        super(scope, id, props);

        // =========================================================================
        // バッチ処理 Lambda (Docker イメージ)
        //
        // 処理内容 (設計書参照):
        //   L1: arXiv API から論文取得 (arxiv_API.md)
        //   L2: pgvector で類似度ベースの選別 (pgvector.md)
        //   L3: Gemini で詳細分析 (LLM_Refinement.md)
        //   Post-L3: PDF全文分析 + 図表抽出 (agent_design.md)
        //
        // セキュリティ (security_architecture.md §5.2):
        //   - Secrets Manager: RDS パスワード + 外部 API キー読み取り
        //   - S3: figures/* への書き込みのみ
        // =========================================================================
        this.batchHandler = new lambda.DockerImageFunction(this, 'BatchHandler', {
            code: lambda.DockerImageCode.fromImageAsset('../backend', {
                file: 'Dockerfile.batch',
            }),
            memorySize: 1024,
            timeout: cdk.Duration.minutes(15),

            // ネットワーク — Private Subnet + sg-batch
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            securityGroups: [props.sgBatch],

            // 環境変数
            environment: {
                DB_SECRET_ARN: props.dbSecret.secretArn,
                FIGURE_BUCKET: props.figureBucket.bucketName,
                // 外部 API キーの ARN は Secrets Manager から取得
                OPENAI_SECRET_ARN: `arn:aws:secretsmanager:${this.region}:${this.account}:secret:ai-research/openai-api-key`,
                GEMINI_SECRET_ARN: `arn:aws:secretsmanager:${this.region}:${this.account}:secret:ai-research/gemini-api-key`,
            },

            // ログ
            logGroup: new logs.LogGroup(this, 'BatchHandlerLogGroup', {
                retention: logs.RetentionDays.TWO_WEEKS,
                removalPolicy: cdk.RemovalPolicy.DESTROY,
            }),

            description: 'Daily batch: arXiv fetch → L2 vector filter → L3 LLM analysis → PDF review → figure extraction',
        });

        // =========================================================================
        // IAM 権限
        // =========================================================================

        // Secrets Manager — DB 接続情報の読み取り
        props.dbSecret.grantRead(this.batchHandler);

        // S3 — figures/* プレフィックスへの書き込みのみ (最小権限)
        props.figureBucket.grantWrite(this.batchHandler, 'figures/*');

        // 外部 API キー用 Secrets Manager の読み取り権限
        // (キー登録後に ARN が確定するため、ワイルドカードでプレフィックスマッチ)
        this.batchHandler.addToRolePolicy(
            new cdk.aws_iam.PolicyStatement({
                actions: ['secretsmanager:GetSecretValue'],
                resources: [
                    `arn:aws:secretsmanager:${this.region}:${this.account}:secret:ai-research/openai-api-key*`,
                    `arn:aws:secretsmanager:${this.region}:${this.account}:secret:ai-research/gemini-api-key*`,
                ],
            }),
        );

        // =========================================================================
        // EventBridge — 日次スケジュール
        //
        // arXiv は UTC 20:00 頃に更新、平日のみ (pgvector.md, iac_cdk_guide)
        // UTC 21:00 (JST 06:00) に実行
        // =========================================================================
        const dailyRule = new events.Rule(this, 'DailyBatchRule', {
            ruleName: 'ai-research-daily-batch',
            description: 'Trigger daily batch at UTC 21:00 (JST 06:00), Mon-Fri',
            schedule: events.Schedule.cron({
                minute: '0',
                hour: '21',
                weekDay: 'MON-FRI', // arXiv は平日のみ更新
            }),
        });

        dailyRule.addTarget(
            new targets.LambdaFunction(this.batchHandler, {
                retryAttempts: 2,
            }),
        );

        // =========================================================================
        // CloudFormation Outputs
        // =========================================================================
        new cdk.CfnOutput(this, 'BatchFunctionName', {
            value: this.batchHandler.functionName,
            description: 'Batch Lambda function name',
            exportName: 'AiResearch-BatchFunctionName',
        });

        new cdk.CfnOutput(this, 'BatchFunctionArn', {
            value: this.batchHandler.functionArn,
            description: 'Batch Lambda function ARN',
            exportName: 'AiResearch-BatchFunctionArn',
        });

        new cdk.CfnOutput(this, 'EventBridgeRuleName', {
            value: dailyRule.ruleName,
            description: 'EventBridge daily batch rule name',
            exportName: 'AiResearch-EventBridgeRuleName',
        });
    }
}
