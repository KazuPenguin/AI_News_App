import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

/**
 * ApiStack に渡す Props
 * NetworkStack, DatabaseStack, AuthStack からの参照を受け取る
 */
export interface ApiStackProps extends cdk.StackProps {
    /** NetworkStack の VPC */
    readonly vpc: ec2.IVpc;
    /** API Lambda 用セキュリティグループ */
    readonly sgLambda: ec2.ISecurityGroup;
    /** RDS 接続用シークレット */
    readonly dbSecret: secretsmanager.ISecret;
    /** Cognito User Pool (Authorizer 用) */
    readonly userPool: cognito.IUserPool;
}

export class ApiStack extends cdk.Stack {
    /** API Lambda 関数 */
    public readonly apiHandler: lambda.Function;

    /** API Gateway REST API */
    public readonly api: apigw.RestApi;

    constructor(scope: Construct, id: string, props: ApiStackProps) {
        super(scope, id, props);

        // =========================================================================
        // API Lambda — 全エンドポイントを単一 Lambda で処理
        //
        // 設計書参照:
        //   - api_specification.md: 12 エンドポイント
        //   - security_architecture.md §5.2: IAM ロール定義
        // =========================================================================
        this.apiHandler = new lambda.DockerImageFunction(this, 'ApiHandler', {
            // Docker Image Deployment
            code: lambda.DockerImageCode.fromImageAsset('../backend', {
                file: 'Dockerfile',
            }),
            memorySize: 512,
            timeout: cdk.Duration.seconds(30),

            // ネットワーク — Private Subnet + sg-lambda
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
            securityGroups: [props.sgLambda],

            // 環境変数
            environment: {
                DB_SECRET_ARN: props.dbSecret.secretArn,
            },

            // ログ
            logRetention: logs.RetentionDays.TWO_WEEKS,

            description: 'API handler for AI Research OS (papers, bookmarks, users)',
        });

        // IAM — Secrets Manager 読み取り
        props.dbSecret.grantRead(this.apiHandler);

        // =========================================================================
        // API Gateway — REST API
        //
        // 設計書参照:
        //   - api_specification.md §1: ベース URL /v1, HTTPS, JSON
        //   - api_specification.md §5.2: レートリミット 100 req/min
        // =========================================================================
        this.api = new apigw.RestApi(this, 'AiResearchApi', {
            restApiName: 'ai-research-api',
            description: 'AI Research OS REST API',
            deployOptions: {
                stageName: 'v1',
                throttlingRateLimit: 100,     // 100 リクエスト/秒 (API 全体)
                throttlingBurstLimit: 200,
                loggingLevel: apigw.MethodLoggingLevel.INFO,
                dataTraceEnabled: false,       // 本番ではリクエストボディのログを無効化
                metricsEnabled: true,
            },
            defaultCorsPreflightOptions: {
                allowOrigins: apigw.Cors.ALL_ORIGINS,
                allowMethods: apigw.Cors.ALL_METHODS,
                allowHeaders: ['Content-Type', 'Authorization'],
                maxAge: cdk.Duration.hours(1),
            },
        });

        // =========================================================================
        // Cognito Authorizer
        // =========================================================================
        const authorizer = new apigw.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
            cognitoUserPools: [props.userPool],
            authorizerName: 'ai-research-cognito-authorizer',
            identitySource: 'method.request.header.Authorization',
        });

        const authMethodOptions: apigw.MethodOptions = {
            authorizer,
            authorizationType: apigw.AuthorizationType.COGNITO,
        };

        // Lambda 統合
        const lambdaIntegration = new apigw.LambdaIntegration(this.apiHandler, {
            proxy: true,
        });

        // =========================================================================
        // エンドポイント定義 (api_specification.md §3)
        // =========================================================================

        // --- /papers ---
        const papers = this.api.root.addResource('papers');
        papers.addMethod('GET', lambdaIntegration, authMethodOptions);           // 論文一覧

        const paper = papers.addResource('{arxiv_id}');
        paper.addMethod('GET', lambdaIntegration, authMethodOptions);            // 論文詳細

        const paperFigures = paper.addResource('figures');
        paperFigures.addMethod('GET', lambdaIntegration, authMethodOptions);     // 図表一覧

        const paperView = paper.addResource('view');
        paperView.addMethod('POST', lambdaIntegration, authMethodOptions);       // 閲覧記録

        // --- /categories ---
        const categories = this.api.root.addResource('categories');
        categories.addMethod('GET', lambdaIntegration, authMethodOptions);       // カテゴリ一覧

        // --- /bookmarks ---
        const bookmarks = this.api.root.addResource('bookmarks');
        bookmarks.addMethod('GET', lambdaIntegration, authMethodOptions);        // お気に入り一覧
        bookmarks.addMethod('POST', lambdaIntegration, authMethodOptions);       // お気に入り追加

        const bookmark = bookmarks.addResource('{id}');
        bookmark.addMethod('DELETE', lambdaIntegration, authMethodOptions);      // お気に入り削除

        // --- /users ---
        const users = this.api.root.addResource('users');
        const me = users.addResource('me');
        me.addMethod('GET', lambdaIntegration, authMethodOptions);               // ユーザー情報

        const settings = me.addResource('settings');
        settings.addMethod('PUT', lambdaIntegration, authMethodOptions);         // 設定更新

        const stats = me.addResource('stats');
        stats.addMethod('GET', lambdaIntegration, authMethodOptions);            // 統計

        // --- /health (認証不要) ---
        const health = this.api.root.addResource('health');
        health.addMethod('GET', lambdaIntegration);                              // ヘルスチェック

        // =========================================================================
        // CloudFormation Outputs
        // =========================================================================
        new cdk.CfnOutput(this, 'ApiUrl', {
            value: this.api.url,
            description: 'API Gateway endpoint URL',
            exportName: 'AiResearch-ApiUrl',
        });

        new cdk.CfnOutput(this, 'ApiId', {
            value: this.api.restApiId,
            description: 'API Gateway REST API ID',
            exportName: 'AiResearch-ApiId',
        });

        new cdk.CfnOutput(this, 'ApiFunctionName', {
            value: this.apiHandler.functionName,
            description: 'API Lambda function name',
            exportName: 'AiResearch-ApiFunctionName',
        });
    }
}
