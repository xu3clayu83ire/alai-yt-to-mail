/**
 * YtToMailBackendStack 單元測試
 *
 * 驗證 CDK Stack 產生的 CloudFormation 資源是否符合規格：
 * - 三張 DynamoDB 資料表存在且設定正確
 * - IAM 角色與 Policy 最小權限
 * - Lambda Function 設定（Runtime、記憶體、Timeout）
 * - Lambda Function URL CORS 設定
 *
 * 測試目的是確保 CDK 程式碼變更不會意外移除或修改關鍵資源設定。
 */
import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { YtToMailBackendStack } from '../lib/yt-to-mail-backend-stack';

describe('YtToMailBackendStack', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new YtToMailBackendStack(app, 'TestYtToMailBackendStack', {
      env: { account: '123456789012', region: 'us-east-1' },
    });
    template = Template.fromStack(stack);
  });

  describe('DynamoDB 資料表', () => {
    test('應建立三張 DynamoDB 資料表', () => {
      template.resourceCountIs('AWS::DynamoDB::Table', 3);
    });

    test('users 資料表應存在 email-index GSI', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'yt-to-mail-users',
        GlobalSecondaryIndexes: [
          {
            IndexName: 'email-index',
            KeySchema: [
              { AttributeName: 'email', KeyType: 'HASH' },
            ],
            Projection: { ProjectionType: 'ALL' },
          },
        ],
      });
    });

    test('subscriptions 資料表應存在 user_id-index GSI', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'yt-to-mail-subscriptions',
        GlobalSecondaryIndexes: [
          {
            IndexName: 'user_id-index',
            KeySchema: [
              { AttributeName: 'user_id', KeyType: 'HASH' },
            ],
            Projection: { ProjectionType: 'ALL' },
          },
        ],
      });
    });

    test('history 資料表應存在含 Sort Key 的 user_id-index GSI', () => {
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'yt-to-mail-history',
        GlobalSecondaryIndexes: [
          {
            IndexName: 'user_id-index',
            KeySchema: [
              { AttributeName: 'user_id', KeyType: 'HASH' },
              { AttributeName: 'sent_at', KeyType: 'RANGE' },
            ],
            Projection: { ProjectionType: 'ALL' },
          },
        ],
      });
    });

    test('所有資料表應使用 PAY_PER_REQUEST 計費模式', () => {
      const tables = template.findResources('AWS::DynamoDB::Table');
      Object.values(tables).forEach((table: any) => {
        expect(table.Properties.BillingMode).toBe('PAY_PER_REQUEST');
      });
    });
  });

  describe('Lambda Function', () => {
    test('應建立 Lambda Function，名稱為 yt-to-mail-api', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'yt-to-mail-api',
        Runtime: 'python3.12',
        Handler: 'main.handler',
        MemorySize: 512,
        Timeout: 30,
        Architectures: ['x86_64'],
      });
    });

    test('Lambda 應設定所有必要的環境變數', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'yt-to-mail-api',
        Environment: {
          Variables: {
            USERS_TABLE: 'yt-to-mail-users',
            SUBSCRIPTIONS_TABLE: 'yt-to-mail-subscriptions',
            HISTORY_TABLE: 'yt-to-mail-history',
            ENVIRONMENT: 'production',
            JWT_EXPIRE_HOURS: '24',
          },
        },
      });
    });
  });

  describe('Lambda Function URL', () => {
    test('應建立 Function URL，AuthType 為 NONE', () => {
      template.hasResourceProperties('AWS::Lambda::Url', {
        AuthType: 'NONE',
      });
    });

    test('Function URL CORS 應允許所有來源', () => {
      template.hasResourceProperties('AWS::Lambda::Url', {
        Cors: {
          AllowOrigins: ['*'],
          AllowHeaders: ['Content-Type', 'Authorization'],
          MaxAge: 3600,
        },
      });
    });
  });

  describe('IAM 角色與政策', () => {
    test('應建立 Lambda IAM 執行角色', () => {
      template.hasResourceProperties('AWS::IAM::Role', {
        RoleName: 'yt-to-mail-api-lambda-role',
        AssumeRolePolicyDocument: {
          Statement: [
            {
              Action: 'sts:AssumeRole',
              Effect: 'Allow',
              Principal: { Service: 'lambda.amazonaws.com' },
            },
          ],
        },
      });
    });

    test('DynamoDB 政策應允許所需操作', () => {
      /**
       * 使用 Match.arrayWith 而非精確陣列比對，
       * 因為 Policy Statement 包含 DynamoDB 與 CloudWatch Logs 兩條規則。
       */
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyName: 'yt-to-mail-dynamodb-policy',
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Effect: 'Allow',
              Action: Match.arrayWith([
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:DeleteItem',
                'dynamodb:Query',
                'dynamodb:Scan',
              ]),
            }),
          ]),
        },
      });
    });
  });

  describe('CloudFormation Outputs', () => {
    test('應輸出 API Endpoint', () => {
      template.hasOutput('ApiEndpoint', {
        Export: {
          Name: 'YtToMailApiEndpoint',
        },
      });
    });
  });
});
