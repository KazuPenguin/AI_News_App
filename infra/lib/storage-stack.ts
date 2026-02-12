import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { Construct } from 'constructs';

export class StorageStack extends cdk.Stack {
    /** 論文図表保管用 S3 バケット — BatchStack で grantWrite に使用 */
    public readonly figureBucket: s3.Bucket;

    /** CloudFront ディストリビューション — 図表配信 URL 生成に使用 */
    public readonly distribution: cloudfront.Distribution;

    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // =========================================================================
        // S3 バケット — 論文図表 (figures/) の保管
        //
        // 設計書参照:
        //   - database_schema.md §2.6: paper_figures テーブル → S3 に画像本体を保管
        //   - database_schema.md §6: 年間 ~10GB ($2.30/年)
        //   - security_architecture.md §4.2: SSE-S3 暗号化
        // =========================================================================
        this.figureBucket = new s3.Bucket(this, 'FigureBucket', {
            bucketName: `ai-research-figures-${cdk.Aws.ACCOUNT_ID}`,
            encryption: s3.BucketEncryption.S3_MANAGED,       // SSE-S3
            blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL, // パブリックアクセス完全ブロック
            versioned: false,                                  // 図表は上書き不要
            removalPolicy: cdk.RemovalPolicy.RETAIN,           // 誤削除防止

            // ライフサイクルルール — 古い図表を低コストストレージに移行
            lifecycleRules: [
                {
                    id: 'TransitionToIA',
                    transitions: [
                        {
                            storageClass: s3.StorageClass.INFREQUENT_ACCESS,
                            transitionAfter: cdk.Duration.days(90),    // 90日後に IA へ移行
                        },
                    ],
                },
            ],

            // CORS — モバイルアプリからの直接画像表示用
            cors: [
                {
                    allowedMethods: [s3.HttpMethods.GET],
                    allowedOrigins: ['*'],
                    allowedHeaders: ['*'],
                    maxAge: 3600,
                },
            ],
        });

        // =========================================================================
        // CloudFront — OAC (Origin Access Control) で S3 にアクセス
        //
        // 設計書参照:
        //   - security_architecture.md §4.1: TLS 1.3
        //   - iac_cdk_guide: キャッシュ TTL 30 日
        // =========================================================================
        this.distribution = new cloudfront.Distribution(this, 'FigureCdn', {
            defaultBehavior: {
                origin: origins.S3BucketOrigin.withOriginAccessControl(this.figureBucket),
                viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cachePolicy: new cloudfront.CachePolicy(this, 'FigureCachePolicy', {
                    cachePolicyName: 'AiResearch-FigureCache',
                    defaultTtl: cdk.Duration.days(30),
                    maxTtl: cdk.Duration.days(365),
                    minTtl: cdk.Duration.days(1),
                }),
                // 画像なのでレスポンスヘッダーポリシーは不要
            },
            comment: 'AI Research OS - Paper figures CDN',
            minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
        });

        // =========================================================================
        // CloudFormation Outputs
        // =========================================================================
        new cdk.CfnOutput(this, 'FigureBucketName', {
            value: this.figureBucket.bucketName,
            description: 'S3 bucket for paper figures',
            exportName: 'AiResearch-FigureBucketName',
        });

        new cdk.CfnOutput(this, 'FigureBucketArn', {
            value: this.figureBucket.bucketArn,
            description: 'S3 bucket ARN',
            exportName: 'AiResearch-FigureBucketArn',
        });

        new cdk.CfnOutput(this, 'CdnDomainName', {
            value: this.distribution.distributionDomainName,
            description: 'CloudFront domain for figure delivery',
            exportName: 'AiResearch-CdnDomainName',
        });

        new cdk.CfnOutput(this, 'CdnDistributionId', {
            value: this.distribution.distributionId,
            description: 'CloudFront distribution ID',
            exportName: 'AiResearch-CdnDistributionId',
        });
    }
}
