#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { DatabaseStack } from '../lib/database-stack';
import { StorageStack } from '../lib/storage-stack';
import { AuthStack } from '../lib/auth-stack';
import { BatchStack } from '../lib/batch-stack';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'ap-northeast-1',
};

// --- 1. NetworkStack (依存なし・最初にデプロイ) ---
const network = new NetworkStack(app, 'NetworkStack', {
  env,
  description: 'VPC, Subnets, NAT Instance, Security Groups',
});

// --- 2. DatabaseStack (依存: NetworkStack) ---
const database = new DatabaseStack(app, 'DatabaseStack', {
  env,
  description: 'RDS PostgreSQL 16 with pgvector support',
  vpc: network.vpc,
  sgRds: network.sgRds,
});

// --- 3. StorageStack (独立) ---
const storage = new StorageStack(app, 'StorageStack', {
  env,
  description: 'S3 bucket for paper figures + CloudFront CDN',
});

// --- 4. AuthStack (独立) ---
const auth = new AuthStack(app, 'AuthStack', {
  env,
  description: 'Cognito User Pool with email/Google/Apple login',
});

// --- 5. BatchStack (依存: Network, Database, Storage) ---
const batch = new BatchStack(app, 'BatchStack', {
  env,
  description: 'Daily batch processing: arXiv → L2 → L3 → figures',
  vpc: network.vpc,
  sgBatch: network.sgBatch,
  dbSecret: database.dbSecret,
  figureBucket: storage.figureBucket,
});

// --- 6. ApiStack (依存: Network, Database, Auth) ---
const api = new ApiStack(app, 'ApiStack', {
  env,
  description: 'REST API with Cognito authentication',
  vpc: network.vpc,
  sgLambda: network.sgLambda,
  dbSecret: database.dbSecret,
  userPool: auth.userPool,
});

