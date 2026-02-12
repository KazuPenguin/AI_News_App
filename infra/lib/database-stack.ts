import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

/**
 * DatabaseStack に渡す Props
 * NetworkStack からの VPC / セキュリティグループを受け取る
 */
export interface DatabaseStackProps extends cdk.StackProps {
    /** NetworkStack の VPC */
    readonly vpc: ec2.IVpc;
    /** RDS 用セキュリティグループ */
    readonly sgRds: ec2.ISecurityGroup;
}

export class DatabaseStack extends cdk.Stack {
    /** RDS インスタンス */
    public readonly dbInstance: rds.DatabaseInstance;

    /** DB 接続用シークレット（Secrets Manager） — 他スタックで grantRead に使用 */
    public readonly dbSecret: secretsmanager.ISecret;

    constructor(scope: Construct, id: string, props: DatabaseStackProps) {
        super(scope, id, props);

        // =========================================================================
        // RDS Parameter Group — pgvector 拡張を許可するカスタムパラメータグループ
        // =========================================================================
        const parameterGroup = new rds.ParameterGroup(this, 'PgParameterGroup', {
            engine: rds.DatabaseInstanceEngine.postgres({
                version: rds.PostgresEngineVersion.VER_16,
            }),
            description: 'AI Research DB - shared_preload_libraries for pgvector',
            parameters: {
                // pgvector のインデックス構築に必要なメモリ設定
                'maintenance_work_mem': '256000',  // 256MB — HNSW インデックス構築用
                // ログ設定
                'log_min_duration_statement': '1000', // 1秒以上のスロークエリを記録
            },
        });

        // =========================================================================
        // RDS PostgreSQL 16 — db.t4g.micro (開発環境)
        //
        // 設計書参照:
        //   - database_schema.md §1: インスタンスタイプ、接続方式
        //   - database_schema.md §6: データ量見積もり → 20GB SSD で数年間余裕
        //   - security_architecture.md §4.2: AES-256 KMS 暗号化
        //   - security_architecture.md §5.1: Secrets Manager でパスワード管理
        // =========================================================================
        this.dbInstance = new rds.DatabaseInstance(this, 'AiResearchDb', {
            engine: rds.DatabaseInstanceEngine.postgres({
                version: rds.PostgresEngineVersion.VER_16,
            }),
            instanceType: ec2.InstanceType.of(
                ec2.InstanceClass.T4G,
                ec2.InstanceSize.MICRO,
            ),
            parameterGroup,

            // --- ネットワーク ---
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            securityGroups: [props.sgRds],

            // --- 認証 (Secrets Manager 自動生成) ---
            credentials: rds.Credentials.fromGeneratedSecret('postgres', {
                secretName: 'ai-research/rds-credentials',
            }),

            // --- データベース ---
            databaseName: 'ai_research',

            // --- ストレージ ---
            allocatedStorage: 20,                         // 20 GB (gp3)
            maxAllocatedStorage: 50,                      // オートスケーリング上限 50GB
            storageType: rds.StorageType.GP3,
            storageEncrypted: true,                       // AES-256 (KMS マネージドキー)

            // --- 可用性 ---
            multiAz: false,                               // 開発環境: false、本番: true に変更

            // --- バックアップ ---
            backupRetention: cdk.Duration.days(7),
            preferredBackupWindow: '18:00-18:30',         // UTC 18:00 = JST 03:00 (低負荷時間帯)
            preferredMaintenanceWindow: 'sun:19:00-sun:19:30', // UTC 日曜 19:00 = JST 月曜 04:00

            // --- モニタリング ---
            enablePerformanceInsights: true,
            performanceInsightRetention: rds.PerformanceInsightRetention.DEFAULT, // 7日間 (無料枠)
            cloudwatchLogsExports: ['postgresql'],         // PostgreSQL ログを CloudWatch に出力

            // --- 開発環境設定 (本番時は変更すること) ---
            deletionProtection: false,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        });

        // シークレットを公開 (BatchStack / ApiStack で grantRead に使用)
        this.dbSecret = this.dbInstance.secret!;

        // =========================================================================
        // CloudFormation Outputs
        // =========================================================================
        new cdk.CfnOutput(this, 'DbEndpoint', {
            value: this.dbInstance.dbInstanceEndpointAddress,
            description: 'RDS PostgreSQL endpoint',
            exportName: 'AiResearch-DbEndpoint',
        });

        new cdk.CfnOutput(this, 'DbPort', {
            value: this.dbInstance.dbInstanceEndpointPort,
            description: 'RDS PostgreSQL port',
            exportName: 'AiResearch-DbPort',
        });

        new cdk.CfnOutput(this, 'DbSecretArn', {
            value: this.dbSecret.secretArn,
            description: 'Secrets Manager ARN for DB credentials',
            exportName: 'AiResearch-DbSecretArn',
        });

        new cdk.CfnOutput(this, 'DbInstanceId', {
            value: this.dbInstance.instanceIdentifier,
            description: 'RDS instance identifier',
            exportName: 'AiResearch-DbInstanceId',
        });
    }
}
