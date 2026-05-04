/**
 * YtToMailBackendStack 單元測試
 *
 * 驗證 CDK Stack 產生的 CloudFormation 資源是否符合規格：
 * - 四張 DynamoDB 資料表存在且設定正確（users、subscriptions、history、channels）
 * - subscriptions 資料表含兩個 GSI（user_id-index、channel_id-index）
 * - channels 資料表 PK 為 channel_id，無 GSI
 * - IAM 角色與 Policy 最小權限（含 index/* ARN）
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
    test('應建立四張 DynamoDB 資料表（users、subscriptions、history、channels）', () => {
      template.resourceCountIs('AWS::DynamoDB::Table', 4);
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

    test('subscriptions 資料表應同時存在 user_id-index 與 channel_id-index 兩個 GSI', () => {
      /**
       * 使用 Match.arrayWith 進行部分比對，
       * 因為 subscriptions 資料表含兩個 GSI，
       * 不限定陣列長度以提高測試可維護性。
       */
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'yt-to-mail-subscriptions',
        GlobalSecondaryIndexes: Match.arrayWith([
          Match.objectLike({
            IndexName: 'user_id-index',
            KeySchema: [
              { AttributeName: 'user_id', KeyType: 'HASH' },
            ],
            Projection: { ProjectionType: 'ALL' },
          }),
          Match.objectLike({
            IndexName: 'channel_id-index',
            KeySchema: [
              { AttributeName: 'channel_id', KeyType: 'HASH' },
            ],
            Projection: { ProjectionType: 'ALL' },
          }),
        ]),
      });
    });

    test('channels 資料表應存在，PK 為 channel_id', () => {
      /**
       * 驗證 step17 新增的頻道白名單資料表存在且 PK 設定正確。
       * channels 資料表無 GSI，使用 GetItem 與 Scan 即可完成所有操作。
       */
      template.hasResourceProperties('AWS::DynamoDB::Table', {
        TableName: 'yt-to-mail-channels',
        KeySchema: [
          { AttributeName: 'channel_id', KeyType: 'HASH' },
        ],
        BillingMode: 'PAY_PER_REQUEST',
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

    test('Lambda 應設定所有必要的環境變數（含 CHANNELS_TABLE）', () => {
      /**
       * 驗證 step17 新增的 CHANNELS_TABLE 環境變數已正確注入 Lambda，
       * 讓 admin_channels router 與 public.py 能取得頻道白名單資料表名稱。
       */
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'yt-to-mail-api',
        Environment: {
          Variables: Match.objectLike({
            USERS_TABLE: 'yt-to-mail-users',
            SUBSCRIPTIONS_TABLE: 'yt-to-mail-subscriptions',
            HISTORY_TABLE: 'yt-to-mail-history',
            CHANNELS_TABLE: 'yt-to-mail-channels',
            ENVIRONMENT: 'production',
            JWT_EXPIRE_HOURS: '24',
          }),
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

  describe('IAM 政策資源 ARN', () => {
    test('DynamoDB 政策資源應包含 index/* ARN（GSI 查詢所需）', () => {
      /**
       * 驗證 step17 補充的 index/* ARN 存在於 DynamoDB Policy resources 中，
       * 確保 channel_id-index GSI 查詢不會因缺少 ARN 而被 IAM 拒絕。
       *
       * CDK 在 synth 時已將 Pseudo Parameter 解析為實際值（因為 env 已指定 account/region），
       * 故以字串結尾比對方式驗證，不依賴 Fn::Join 結構。
       */
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: { PolicyName: 'yt-to-mail-dynamodb-policy' },
      });
      const policyKeys = Object.keys(policies);
      expect(policyKeys.length).toBe(1);

      const statements: Array<{ Resource?: string[] }> = policies[policyKeys[0]].Properties.PolicyDocument.Statement;
      const dynamoStatement = statements.find((s) =>
        Array.isArray(s.Resource) &&
        s.Resource.some((r: string) => typeof r === 'string' && r.includes('yt-to-mail-*/index/*'))
      );
      expect(dynamoStatement).toBeDefined();
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

    test('應輸出 ChannelsTableName', () => {
      /**
       * 驗證 step17 新增的 ChannelsTableName CfnOutput 存在，
       * 供部署後確認資料表名稱。
       */
      template.hasOutput('ChannelsTableName', {});
    });
  });
});
