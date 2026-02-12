import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';

export class AuthStack extends cdk.Stack {
    /** Cognito User Pool — ApiStack で Authorizer に使用 */
    public readonly userPool: cognito.UserPool;

    /** App Client — フロントエンドから認証に使用 */
    public readonly appClient: cognito.UserPoolClient;

    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // =========================================================================
        // Cognito User Pool
        //
        // 設計書参照:
        //   - security_architecture.md §3.1: メール + Google + Apple
        //   - security_architecture.md §3.1: OAuth 2.0 Authorization Code + PKCE
        //   - security_architecture.md §3.1: ID Token 1h, Refresh Token 30d
        // =========================================================================
        this.userPool = new cognito.UserPool(this, 'AiResearchUserPool', {
            userPoolName: 'ai-research-user-pool',
            selfSignUpEnabled: true,
            signInAliases: { email: true },
            autoVerify: { email: true },

            // パスワードポリシー
            passwordPolicy: {
                minLength: 8,
                requireLowercase: true,
                requireUppercase: true,
                requireDigits: true,
                requireSymbols: false,
            },

            // アカウント復旧
            accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,

            // ユーザー属性
            standardAttributes: {
                email: { required: true, mutable: true },
                fullname: { required: false, mutable: true },
            },
            customAttributes: {
                auth_provider: new cognito.StringAttribute({ mutable: false }),
            },

            // メール送信（Cognito デフォルト）
            // 本番では SES に切り替えを検討
            email: cognito.UserPoolEmail.withCognito(),

            removalPolicy: cdk.RemovalPolicy.RETAIN,
        });

        // =========================================================================
        // Google ソーシャルログイン
        //
        // NOTE: クレデンシャルは Secrets Manager から取得
        //       → あとでやること.md 参照
        // =========================================================================
        // Google Provider は OAuth クレデンシャル取得後に有効化
        // const googleProvider = new cognito.UserPoolIdentityProviderGoogle(this, 'Google', {
        //   userPool: this.userPool,
        //   clientId: '<GOOGLE_CLIENT_ID>',
        //   clientSecretValue: cdk.SecretValue.secretsManager('ai-research/google-oauth-secret'),
        //   scopes: ['openid', 'email', 'profile'],
        //   attributeMapping: {
        //     email: cognito.ProviderAttribute.GOOGLE_EMAIL,
        //     fullname: cognito.ProviderAttribute.GOOGLE_NAME,
        //   },
        // });

        // =========================================================================
        // Apple ソーシャルログイン
        // =========================================================================
        // Apple Provider は OAuth クレデンシャル取得後に有効化
        // const appleProvider = new cognito.UserPoolIdentityProviderApple(this, 'Apple', {
        //   userPool: this.userPool,
        //   clientId: '<APPLE_SERVICE_ID>',
        //   teamId: '<APPLE_TEAM_ID>',
        //   keyId: '<APPLE_KEY_ID>',
        //   privateKey: '<APPLE_PRIVATE_KEY>',
        //   scopes: ['openid', 'email', 'name'],
        //   attributeMapping: {
        //     email: cognito.ProviderAttribute.APPLE_EMAIL,
        //     fullname: cognito.ProviderAttribute.APPLE_NAME,
        //   },
        // });

        // =========================================================================
        // App Client — Authorization Code + PKCE
        // =========================================================================
        this.appClient = this.userPool.addClient('MobileApp', {
            userPoolClientName: 'ai-research-mobile-app',
            oAuth: {
                flows: { authorizationCodeGrant: true },
                scopes: [
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callbackUrls: ['myapp://callback'],
                logoutUrls: ['myapp://signout'],
            },
            authFlows: { userSrp: true },
            idTokenValidity: cdk.Duration.hours(1),
            refreshTokenValidity: cdk.Duration.days(30),
            accessTokenValidity: cdk.Duration.hours(1),
            supportedIdentityProviders: [
                cognito.UserPoolClientIdentityProvider.COGNITO,
                // Google / Apple はクレデンシャル設定後にここに追加
                // cognito.UserPoolClientIdentityProvider.GOOGLE,
                // cognito.UserPoolClientIdentityProvider.APPLE,
            ],
            preventUserExistenceErrors: true,
        });

        // =========================================================================
        // Hosted UI ドメイン
        // =========================================================================
        this.userPool.addDomain('CognitoDomain', {
            cognitoDomain: { domainPrefix: 'ai-research-os' },
        });

        // =========================================================================
        // CloudFormation Outputs
        // =========================================================================
        new cdk.CfnOutput(this, 'UserPoolId', {
            value: this.userPool.userPoolId,
            description: 'Cognito User Pool ID',
            exportName: 'AiResearch-UserPoolId',
        });

        new cdk.CfnOutput(this, 'UserPoolArn', {
            value: this.userPool.userPoolArn,
            description: 'Cognito User Pool ARN',
            exportName: 'AiResearch-UserPoolArn',
        });

        new cdk.CfnOutput(this, 'AppClientId', {
            value: this.appClient.userPoolClientId,
            description: 'Cognito App Client ID',
            exportName: 'AiResearch-AppClientId',
        });

        new cdk.CfnOutput(this, 'CognitoDomainUrl', {
            value: `https://ai-research-os.auth.${this.region}.amazoncognito.com`,
            description: 'Cognito Hosted UI URL',
            exportName: 'AiResearch-CognitoDomainUrl',
        });
    }
}
