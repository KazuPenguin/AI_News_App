# CI/CD 現在の実装状況 (Current Implementation Status)

現在のGitHub ActionsワークフローとAWS CDKの実装に基づいた構成図です。

## 1. 全体フロー (Overview)

```mermaid
graph TD
    subgraph GitHub_Actions [GitHub Actions]
        direction TB
        
        %% Triggers
        PushMain([Push to main]) --> CI_Flow
        PushMain --> Deploy_Flow
        PushMain --> Security_Flow
        
        PR([Pull Request]) --> CI_Flow
        PR --> Security_Flow
        
        %% Workflows
        subgraph CI_Workflow ["CI (ci.yml)"]
            Ruff[Backend: Ruff Lint/Format]
            CDK_Check[Infra: TypeScript Check & Test]
            CDK_Synth[Infra: CDK Synth]
            
            Ruff --> CDK_Check
            CDK_Check --> CDK_Synth
        end
        
        subgraph Deploy_Workflow ["Deploy (deploy.yml)"]
            CDK_Diff[Infra: CDK Diff]
            CDK_Deploy[Infra: CDK Deploy]
            
            CDK_Diff -- "Manual Approval (Environment)" --> CDK_Deploy
        end
        
        subgraph Security_Workflow ["Security (security.yml)"]
            TruffleHog[Secret Scan]
        end
    end
    
    subgraph AWS_Cloud [AWS Cloud]
        Lambda["Lambda Function (Python)"]
        APIGW[API Gateway]
        Resources["Other Resources (DynamoDB/Cognito/etc)"]
        
        CDK_Deploy -- "Update (Zip)" --> Lambda
        CDK_Deploy -- Provision --> APIGW
        CDK_Deploy -- Provision --> Resources
    end
    
    %% Relationships
    CI_Flow -.-> Deploy_Flow
```

## 2. 詳細: Backend & Infra Deploy Flow (Current)

現状の実装では、Backendコード（Python）はDockerコンテナではなく、CDKによって**Zipアセット**としてLambdaにデプロイされています。

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub Actions (Deploy)
    participant AWS as AWS CloudFormation
    participant Lambda as AWS Lambda
    
    Dev->>GH: Push to main (Backend/Infra code)
    
    rect rgb(240, 240, 240)
        Note over GH: deploy.yml
        GH->>GH: Checkout Code
        GH->>GH: NPM CI (Install CDK)
        GH->>GH: Configure AWS Creds (OIDC)
        GH->>GH: CDK Diff (Check Changes)
    end
    
    Dev->>GH: Approve Deployment (if configured)
    
    rect rgb(220, 240, 255)
        Note over GH: CDK Deploy
        GH->>GH: Zip Backend Code (`backend/api`)
        GH->>GH: Upload Zip to S3 (CDK Assets)
        GH->>AWS: Deploy CloudFormation Stack
    end
    
    AWS->>Lambda: Update Function Code (from S3 Zip)
    AWS-->>GH: Deployment Success
```

## 3. 課題 (Gap Analysis)

| 機能 | 設計 (Specification) | 現状 (Current Implementation) | 乖離 (Gap) |
| :--- | :--- | :--- | :--- |
| **Backend Deploy** | Docker Image (ECR) + Lambda Container | Zip Asset Upload | **要対応** (Docker化 or 設計変更) |
| **Backend Test** | pytest, mypy | 未実装 | **要追加** |
| **Frontend CI/CD** | Lint, Test, Build (EAS/Fastlane) | 未実装 | **要新規作成** |
