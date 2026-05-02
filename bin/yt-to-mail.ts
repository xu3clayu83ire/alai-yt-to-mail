#!/usr/bin/env node
/**
 * CDK 應用程式入口點
 * 負責初始化 CDK App 並掛載 YtToMailBackendStack 與 YtToMailFrontendStack。
 *
 * 部署流程說明：
 * 1. 首次部署：cdk deploy --all（BackendStack 先部署，Frontend 後部署）
 * 2. 取得 CloudFront 網域後，重新部署 Backend 以限縮 CORS：
 *    cdk deploy YtToMailBackendStack --context allowedOrigin=https://xxx.cloudfront.net
 */
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { YtToMailBackendStack } from '../lib/yt-to-mail-backend-stack';
import { YtToMailFrontendStack } from '../lib/yt-to-mail-frontend-stack';

const app = new cdk.App();

/**
 * 從 CDK Context 讀取 allowedOrigin（可選）
 * 初始部署不傳此參數，預設為 "*"。
 * Phase 4 完成後以 --context 傳入 CloudFront 網域以限縮 CORS。
 */
const allowedOrigin = app.node.tryGetContext('allowedOrigin') as string | undefined;

new YtToMailBackendStack(app, 'YtToMailBackendStack', {
  description: 'yt-to-mail 雲端後端：Lambda Function URL + DynamoDB',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  allowedOrigin,
});

new YtToMailFrontendStack(app, 'YtToMailFrontendStack', {
  description: 'yt-to-mail 前端：S3 + CloudFront',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
