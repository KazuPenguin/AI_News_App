# VPC / ネットワーク設計解説

> **対象ファイル**: `infra/lib/network-stack.ts`（132行）
> **作成日**: 2026-02-19

---

## 1. 全体構成

```mermaid
graph TB
    subgraph VPC["VPC: 10.0.0.0/16 — AiResearchVpc (ap-northeast-1)"]
        subgraph AZa["AZ-a"]
            subgraph PubA["Public Subnet /24"]
                IGW["Internet Gateway"]
                NAT["NAT Gateway"]
            end
            subgraph PriA["Private Subnet /24 (PRIVATE_WITH_EGRESS)"]
                LambdaA["API Lambda<br/>(sg-lambda)"]
                BatchA["Batch Lambda<br/>(sg-batch)"]
                RDSpri["RDS Primary<br/>(sg-rds)"]
            end
        end
        subgraph AZc["AZ-c"]
            subgraph PubC["Public Subnet /24"]
                PubC_note["(NAT なし)"]
            end
            subgraph PriC["Private Subnet /24 (PRIVATE_WITH_EGRESS)"]
                LambdaC["API Lambda<br/>(sg-lambda)"]
                BatchC["Batch Lambda<br/>(sg-batch)"]
                RDSstb["RDS Standby<br/>(Multi-AZ 時)"]
            end
        end
    end

    Internet(("Internet"))
    Internet --> IGW
    IGW --> NAT
    NAT --> PriA
    NAT --> PriC

    style VPC fill:#e8f4f8,stroke:#2196F3,stroke-width:2px
    style AZa fill:#fff3e0,stroke:#FF9800
    style AZc fill:#fff3e0,stroke:#FF9800
    style PubA fill:#c8e6c9,stroke:#4CAF50
    style PubC fill:#c8e6c9,stroke:#4CAF50
    style PriA fill:#e1bee7,stroke:#9C27B0
    style PriC fill:#e1bee7,stroke:#9C27B0
```

> **補足**: CDK の `cidrMask: 24` と `maxAzs: 2` 指定により、CDK がサブネット CIDR を自動割当する。

---

## 2. VPC 設定詳細

| 項目 | 値 | 備考 |
|:---|:---|:---|
| **CIDR** | `10.0.0.0/16` | 65,536 IP アドレス |
| **AZ 数** | 2 | `maxAzs: 2` で ap-northeast-1a/1c を使用 |
| **Public サブネット** | 2（各 AZ に 1 つ） | NAT Gateway、Internet Gateway の配置先 |
| **Private サブネット** | 2（各 AZ に 1 つ） | `PRIVATE_WITH_EGRESS` — NAT 経由で外部通信可能 |
| **NAT Gateway** | **1 つのみ** | コスト対策（約 $32/月）。本番では 2 つに増やすべき |
| **Internet Gateway** | CDK 自動作成 | Public サブネット作成時に自動付与 |

### なぜ PRIVATE_WITH_EGRESS か

Lambda と RDS はプライベートサブネットに配置し、インターネットからの直接アクセスを遮断する。
一方で Lambda は以下の外部通信が必要なため、NAT Gateway 経由のアウトバウンド通信を許可している:

- **API Lambda**: AWS サービス（Secrets Manager, CloudWatch 等）への HTTPS 呼び出し
- **Batch Lambda**: arXiv API、OpenAI API、Gemini API への HTTPS 呼び出し

---

## 3. セキュリティグループ

3 つのセキュリティグループを定義し、最小権限の原則で通信を制御している。
全て `allowAllOutbound: false` で明示的にアウトバウンドを制限している点がポイント。

### sg-lambda（API Lambda 用）

| 方向 | プロトコル | ポート | 対象 | 用途 |
|:---|:---|:---|:---|:---|
| **Egress** | TCP | 443 | `0.0.0.0/0` | HTTPS（AWS サービス、外部 API） |
| **Egress** | TCP | 5432 | `sg-rds` | PostgreSQL 接続 |
| **Ingress** | — | — | — | なし（API Gateway → Lambda は VPC 外で呼び出される） |

### sg-batch（バッチ Lambda 用）

| 方向 | プロトコル | ポート | 対象 | 用途 |
|:---|:---|:---|:---|:---|
| **Egress** | TCP | 443 | `0.0.0.0/0` | HTTPS（arXiv / OpenAI / Gemini API） |
| **Egress** | TCP | 5432 | `sg-rds` | PostgreSQL 接続 |
| **Ingress** | — | — | — | なし（EventBridge → Lambda は VPC 外で呼び出される） |

### sg-rds（RDS PostgreSQL 用）

| 方向 | プロトコル | ポート | 対象 | 用途 |
|:---|:---|:---|:---|:---|
| **Ingress** | TCP | 5432 | `sg-lambda` | API Lambda からの DB 接続 |
| **Ingress** | TCP | 5432 | `sg-batch` | Batch Lambda からの DB 接続 |
| **Egress** | — | — | — | なし（DB はアウトバウンド不要） |

### セキュリティグループ間の通信フロー

```mermaid
flowchart LR
    User(("ユーザー"))
    APIGW["API Gateway"]
    EB["EventBridge<br/>平日 UTC 21:00"]

    subgraph SG_Lambda["sg-lambda"]
        APILambda["API Lambda"]
    end

    subgraph SG_Batch["sg-batch"]
        BatchLambda["Batch Lambda"]
    end

    subgraph SG_RDS["sg-rds"]
        RDS[("RDS PostgreSQL<br/>+ pgvector")]
    end

    ExtAPI["外部 API<br/>arXiv / OpenAI / Gemini"]
    AWSsvc["AWS Services<br/>Secrets Manager<br/>CloudWatch"]

    User -->|HTTPS| APIGW
    APIGW -->|invoke| APILambda
    EB -->|invoke| BatchLambda

    APILambda -->|"TCP 5432"| RDS
    BatchLambda -->|"TCP 5432"| RDS

    APILambda -->|"TCP 443<br/>NAT GW 経由"| AWSsvc
    BatchLambda -->|"TCP 443<br/>NAT GW 経由"| ExtAPI
    BatchLambda -->|"TCP 443<br/>NAT GW 経由"| AWSsvc

    style SG_Lambda fill:#e3f2fd,stroke:#1565C0,stroke-width:2px
    style SG_Batch fill:#e8f5e9,stroke:#2E7D32,stroke-width:2px
    style SG_RDS fill:#fce4ec,stroke:#C62828,stroke-width:2px
    style RDS fill:#fce4ec,stroke:#C62828
```

---

## 4. CloudFormation Outputs

他スタックからの参照やコンソール確認のため、以下の値をエクスポートしている:

| Output 名 | Export 名 | 内容 |
|:---|:---|:---|
| `VpcId` | `AiResearch-VpcId` | VPC の ID |
| `SgLambdaId` | `AiResearch-SgLambdaId` | API Lambda 用 SG の ID |
| `SgBatchId` | `AiResearch-SgBatchId` | Batch Lambda 用 SG の ID |
| `SgRdsId` | `AiResearch-SgRdsId` | RDS 用 SG の ID |

---

## 5. 他スタックとの依存関係

NetworkStack は全スタックの基盤であり、以下のスタックがプロパティ経由で VPC / SG を受け取る:

```mermaid
flowchart TD
    Net["NetworkStack<br/>VPC / SG 定義"]
    DB["DatabaseStack<br/>RDS PostgreSQL 16"]
    API["ApiStack<br/>API Lambda + API GW"]
    Batch["BatchStack<br/>Batch Lambda + EventBridge"]
    Store["StorageStack<br/>S3 + CloudFront"]
    Auth["AuthStack<br/>Cognito User Pool"]

    Net -->|"vpc, sgRds"| DB
    Net -->|"vpc, sgLambda"| API
    Net -->|"vpc, sgBatch"| Batch
    DB -->|"dbSecret"| API
    DB -->|"dbSecret"| Batch
    Store -->|"figureBucket"| Batch
    Auth -->|"userPool"| API

    style Net fill:#e3f2fd,stroke:#1565C0,stroke-width:2px
    style DB fill:#fce4ec,stroke:#C62828
    style API fill:#e8f5e9,stroke:#2E7D32
    style Batch fill:#fff3e0,stroke:#E65100
    style Store fill:#f3e5f5,stroke:#7B1FA2
    style Auth fill:#fffde7,stroke:#F9A825
```

---

## 6. 本番環境に向けた考慮事項

| 項目 | 現状（開発） | 本番推奨 |
|:---|:---|:---|
| **NAT Gateway 数** | 1（片方の AZ のみ） | 2（各 AZ に 1 つ。可用性向上） |
| **NAT Gateway コスト** | 約 $32/月 | 約 $64/月 |
| **RDS Multi-AZ** | false | true（自動フェイルオーバー） |
| **VPC Flow Logs** | 未設定 | 有効化（監査・トラブルシュート用） |
| **VPC Endpoints** | 未設定 | S3, Secrets Manager 等に追加（NAT 経由の通信削減・コスト最適化） |
| **Network ACL** | デフォルト（全許可） | 必要に応じてサブネット単位の制御を追加 |
