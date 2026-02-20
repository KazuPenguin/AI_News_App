# CDK スタック アーキテクチャ図

## スタック間の依存関係

```mermaid
graph TD
    subgraph Independent["独立スタック"]
        direction LR
        Network["🌐 NetworkStack"]
        Storage["📦 StorageStack"]
        Auth["🔐 AuthStack"]
    end

    subgraph Dependent["依存スタック"]
        Database["🗄️ DatabaseStack"]
        Batch["⏰ BatchStack"]
        Api["🚀 ApiStack"]
    end

    Network -->|vpc, sgRds| Database
    Network -->|vpc, sgBatch| Batch
    Network -->|vpc, sgLambda| Api
    Database -->|dbSecret| Batch
    Database -->|dbSecret| Api
    Storage -->|figureBucket| Batch
    Auth -->|userPool| Api

    style Network fill:#4a90d9,stroke:#2c5ea0,color:#fff
    style Database fill:#e67e22,stroke:#c0651a,color:#fff
    style Storage fill:#27ae60,stroke:#1e8449,color:#fff
    style Auth fill:#8e44ad,stroke:#6c3483,color:#fff
    style Batch fill:#e74c3c,stroke:#c0392b,color:#fff
    style Api fill:#f39c12,stroke:#d4870e,color:#fff
```

## 各スタックの中身

```mermaid
graph TB
    subgraph NS["🌐 NetworkStack"]
        direction TB
        VPC["VPC 10.0.0.0/16　2 AZ 構成"]
        PubSub["Public Subnet ×2　+ NAT Gateway"]
        PriSub["Private Subnet ×2　Lambda / RDS 配置"]
        SG_L["sg-lambda"]
        SG_B["sg-batch"]
        SG_R["sg-rds　Inbound: 5432　from sg-lambda, sg-batch"]
        VPC --- PubSub
        VPC --- PriSub
        VPC --- SG_L
        VPC --- SG_B
        VPC --- SG_R
    end

    subgraph DS["🗄️ DatabaseStack"]
        direction TB
        RDS["RDS PostgreSQL 16　db.t4g.micro"]
        SM["Secrets Manager　DB パスワード自動生成"]
        PGV["pgvector 拡張　デプロイ後に有効化"]
        ENC["AES-256 暗号化　KMS マネージド"]
        RDS --- SM
        RDS --- PGV
        RDS --- ENC
    end

    subgraph SS["📦 StorageStack"]
        direction TB
        S3["S3 バケット　ai-research-figures　SSE-S3 暗号化"]
        CF["CloudFront　OAC 経由アクセス　TTL 30日"]
        S3 --- CF
    end

    subgraph AS["🔐 AuthStack"]
        direction TB
        UP["Cognito User Pool　メール + パスワード"]
        GP["Google Provider　OAuth 連携"]
        AP["Apple Provider　OAuth 連携"]
        AC["App Client　Authorization Code + PKCE　ID Token: 1h / Refresh: 30d"]
        HD["Hosted UI ドメイン　ai-research-os"]
        UP --- GP
        UP --- AP
        UP --- AC
        UP --- HD
    end

    subgraph BS["⏰ BatchStack"]
        direction TB
        BL["Batch Lambda　Docker Image　1024MB / 15min timeout"]
        EB["EventBridge Rule　cron: 毎日 UTC 21:00　月〜金のみ"]
        IAM_B["IAM 権限　Secrets Manager 読取　S3 figures/* 書込"]
        EB -->|トリガー| BL
        BL --- IAM_B
    end

    subgraph APS["🚀 ApiStack"]
        direction TB
        APIGW["API Gateway　REST API"]
        AL["API Lambda　VPC Private Subnet"]
        CAuth["Cognito Authorizer　JWT 検証"]
        IAM_A["IAM 権限　Secrets Manager 読取　RDS 接続"]
        APIGW -->|認証| CAuth
        APIGW -->|ルーティング| AL
        AL --- IAM_A
    end

    style NS fill:#eaf2fb,stroke:#4a90d9
    style DS fill:#fdf2e9,stroke:#e67e22
    style SS fill:#eafaf1,stroke:#27ae60
    style AS fill:#f4ecf7,stroke:#8e44ad
    style BS fill:#fdedec,stroke:#e74c3c
    style APS fill:#fef9e7,stroke:#f39c12
```

## デプロイ順序

```mermaid
flowchart LR
    N["1️⃣ NetworkStack"] --> D["2️⃣ DatabaseStack"]
    N --> S["3️⃣ StorageStack"]
    N --> A["4️⃣ AuthStack"]
    D --> B["5️⃣ BatchStack"]
    S --> B
    D --> API["6️⃣ ApiStack"]
    A --> API

    style N fill:#4a90d9,color:#fff,stroke:#2c5ea0
    style D fill:#e67e22,color:#fff,stroke:#c0651a
    style S fill:#27ae60,color:#fff,stroke:#1e8449
    style A fill:#8e44ad,color:#fff,stroke:#6c3483
    style B fill:#e74c3c,color:#fff,stroke:#c0392b
    style API fill:#f39c12,color:#fff,stroke:#d4870e
```

> [!NOTE]
> `StorageStack` と `AuthStack` は `NetworkStack` に依存しないため、`NetworkStack` と並行してデプロイ可能です。ただし `BatchStack` と `ApiStack` はすべての上流スタックが完了してから実行してください。
