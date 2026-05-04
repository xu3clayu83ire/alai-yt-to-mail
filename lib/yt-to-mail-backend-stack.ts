/**
 * YtToMailBackendStack
 *
 * 建立 yt-to-mail 系統的雲端後端基礎設施：
 * - 三張 DynamoDB 資料表（users、subscriptions、history）及各自的 GSI
 * - IAM Lambda 執行角色（最小權限，僅允許操作 yt-to-mail-* 表）
 * - Lambda Function（Python 3.12、FastAPI + Mangum）
 * - Lambda Function URL（AuthType NONE，JWT 由應用層驗證）
 * - CfnOutput 輸出 Function URL 供前端使用
 *
 * 使用此 Stack 的原因：
 * 原型階段採用單一 Lambda + Function URL 取代 API Gateway，
 * 可節省 API Gateway 費用並簡化部署鏈路。
 */
import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { Construct } from 'constructs';

/**
 * YtToMailBackendStackProps
 * 擴充標準 StackProps，加入 allowedOrigin 參數，
 * 供 Phase 4 部署後將 CORS AllowOrigins 限縮至 CloudFront 網域使用。
 * 預設值為 "*"，原型階段初始部署使用。
 *
 * adminEmail / adminPasswordHash：
 * 管理員帳號憑證從 CDK Context 注入，絕不硬編碼於程式碼中。
 * 部署時以 --context adminEmail=xxx --context adminPasswordHash=yyy 傳入。
 * 空字串代表管理員功能停用（login 路由不進入 admin 分支）。
 */
interface YtToMailBackendStackProps extends cdk.StackProps {
  allowedOrigin?: string;
  adminEmail?: string;
  adminPasswordHash?: string;
  jwtSecretKey?: string;
}

export class YtToMailBackendStack extends cdk.Stack {
  /**
   * Lambda Function URL 供外部 Stack 或 CfnOutput 使用
   */
  public readonly functionUrl: lambda.FunctionUrl;

  constructor(scope: Construct, id: string, props?: YtToMailBackendStackProps) {
    super(scope, id, props);
    const allowedOrigin = props?.allowedOrigin ?? '*';
    const adminEmail = props?.adminEmail ?? '';
    const adminPasswordHash = props?.adminPasswordHash ?? '';
    const jwtSecretKey = props?.jwtSecretKey ?? '';

    // =========================================================
    // Step 1：建立三張 DynamoDB 資料表
    // =========================================================

    /**
     * users 資料表
     * 儲存用戶帳號與 bcrypt 密碼雜湊，
     * 透過 email-index GSI 支援以 email 查詢用戶（登入驗證）。
     */
    const usersTable = new dynamodb.Table(this, 'UsersTable', {
      tableName: 'yt-to-mail-users',
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: false,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    usersTable.addGlobalSecondaryIndex({
      indexName: 'email-index',
      partitionKey: {
        name: 'email',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    /**
     * subscriptions 資料表
     * 儲存用戶對 YouTube 頻道的訂閱設定（收件信箱、語速、發送時間等），
     * 透過 user_id-index GSI 支援以 user_id 查詢該用戶所有訂閱。
     */
    const subscriptionsTable = new dynamodb.Table(this, 'SubscriptionsTable', {
      tableName: 'yt-to-mail-subscriptions',
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    subscriptionsTable.addGlobalSecondaryIndex({
      indexName: 'user_id-index',
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    /**
     * history 資料表
     * 記錄每次排程任務的執行結果（成功、失敗、略過），
     * 透過 user_id-index GSI（含 sent_at Sort Key）支援以時間降冪查詢歷史。
     */
    const historyTable = new dynamodb.Table(this, 'HistoryTable', {
      tableName: 'yt-to-mail-history',
      partitionKey: {
        name: 'id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    historyTable.addGlobalSecondaryIndex({
      indexName: 'user_id-index',
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'sent_at',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    /**
     * channels 資料表：管理員維護的可訂閱頻道白名單
     * 使用 channel_id 作為 Partition Key，讓 GetItem 可直接查詢單一頻道，
     * 無需 GSI 即可完成 CRUD 操作；全表 Scan 數量小規模可接受。
     */
    const channelsTable = new dynamodb.Table(this, 'ChannelsTable', {
      tableName: 'yt-to-mail-channels',
      partitionKey: {
        name: 'channel_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    /**
     * subscriptions 資料表補充 channel_id-index GSI
     * 管理員刪除頻道時，以 channel_id 快速查詢所有相關訂閱並串聯取消，
     * 避免全表 Scan 效率低落；此 GSI 在 cdk deploy 時線上新增，現有資料不受影響。
     */
    subscriptionsTable.addGlobalSecondaryIndex({
      indexName: 'channel_id-index',
      partitionKey: {
        name: 'channel_id',
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // =========================================================
    // Step 2：建立 IAM Lambda 執行角色（最小權限原則）
    // =========================================================

    /**
     * Lambda 執行角色
     * 僅授予操作 yt-to-mail-* 資料表的必要 DynamoDB 動作，
     * 以及 CloudWatch Logs 寫入權限（Lambda 基本執行需求）。
     * 明確排除 wildcard 資源，確保安全邊界。
     */
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      roleName: 'yt-to-mail-api-lambda-role',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'yt-to-mail API Lambda execution role - DynamoDB access for yt-to-mail-* tables only',
    });

    // DynamoDB 最小權限：僅允許操作 yt-to-mail-* 表及其 GSI
    const dynamoPolicy = new iam.Policy(this, 'DynamoDbPolicy', {
      policyName: 'yt-to-mail-dynamodb-policy',
      statements: [
        new iam.PolicyStatement({
          sid: 'DynamoDbTableAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
            'dynamodb:DeleteItem',
            'dynamodb:Query',
            'dynamodb:Scan',
          ],
          resources: [
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-*`,
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-*/index/*`,
          ],
        }),
        new iam.PolicyStatement({
          sid: 'CloudWatchLogsAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
          ],
          resources: [
            `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/lambda/yt-to-mail-*`,
          ],
        }),
      ],
    });

    lambdaRole.attachInlinePolicy(dynamoPolicy);

    // =========================================================
    // Step 3：建立 Lambda Function
    // =========================================================

    /**
     * Lambda Function
     * 使用 Python 3.12 Runtime，以 FastAPI + Mangum 提供 RESTful API。
     * CDK bundling 在部署前自動執行 pip install，確保依賴套件打包在一起。
     * JWT_SECRET_KEY 必須在部署後手動設定或透過 Secrets Manager 注入，
     * 預設值為空字串（部署後若未設定將導致 JWT 功能無法使用）。
     */
    const apiFunction = new lambda.Function(this, 'ApiFunction', {
      functionName: 'yt-to-mail-api',
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.X86_64,
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      handler: 'main.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/api'), {
        bundling: {
          /**
           * CDK 部署時自動執行 pip install
           * 將 requirements.txt 中的套件安裝到 Lambda 部署目錄，
           * 確保 FastAPI、Mangum、python-jose 等依賴一起打包。
           */
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -r . /asset-output && rm -rf /asset-output/.venv',
          ],
        },
      }),
      role: lambdaRole,
      environment: {
        JWT_SECRET_KEY: jwtSecretKey,
        JWT_EXPIRE_HOURS: '24',
        USERS_TABLE: 'yt-to-mail-users',
        SUBSCRIPTIONS_TABLE: 'yt-to-mail-subscriptions',
        HISTORY_TABLE: 'yt-to-mail-history',
        CHANNELS_TABLE: 'yt-to-mail-channels',
        ENVIRONMENT: 'production',
        // 管理員憑證從 CDK Context 注入，空字串代表停用管理員登入分支
        ADMIN_EMAIL: adminEmail,
        ADMIN_PASSWORD_HASH: adminPasswordHash,
      },
      description: 'yt-to-mail API: FastAPI + Mangum, handles auth, subscriptions CRUD, history',
    });

    // =========================================================
    // Step 4：啟用 Lambda Function URL（AuthType NONE，CORS 設定）
    // =========================================================

    /**
     * Lambda Function URL
     * 使用 AuthType NONE 因為 JWT 認證由 FastAPI 應用層自行處理，
     * 無需 IAM 簽名（前端瀏覽器無法輕易執行 AWS Signature V4）。
     * CORS AllowOrigins 原型階段設為 ["*"]，Phase 4 改為 CloudFront 網域。
     */
    this.functionUrl = apiFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: [allowedOrigin],
        allowedMethods: [
          lambda.HttpMethod.GET,
          lambda.HttpMethod.POST,
          lambda.HttpMethod.PUT,
          lambda.HttpMethod.PATCH,
          lambda.HttpMethod.DELETE,
          lambda.HttpMethod.HEAD,
        ],
        allowedHeaders: ['Content-Type', 'Authorization'],
        maxAge: cdk.Duration.seconds(3600),
      },
    });

    // =========================================================
    // Step 16：CfnOutput 輸出 Function URL 供前端與排程器使用
    // =========================================================

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.functionUrl.url,
      description: 'yt-to-mail API Lambda Function URL',
      exportName: 'YtToMailApiEndpoint',
    });

    new cdk.CfnOutput(this, 'UsersTableName', {
      value: usersTable.tableName,
      description: 'DynamoDB users 資料表名稱',
    });

    new cdk.CfnOutput(this, 'SubscriptionsTableName', {
      value: subscriptionsTable.tableName,
      description: 'DynamoDB subscriptions 資料表名稱',
    });

    new cdk.CfnOutput(this, 'HistoryTableName', {
      value: historyTable.tableName,
      description: 'DynamoDB history 資料表名稱',
    });

    new cdk.CfnOutput(this, 'ChannelsTableName', {
      value: channelsTable.tableName,
      description: 'DynamoDB channels 資料表名稱',
    });

    // =========================================================
    // Step 5：建立本機排程器專用 IAM User 與 Policy（最小權限）
    // =========================================================

    /**
     * 本機排程器 IAM Policy
     * 僅授予 subscriptions 表讀取與 history 表寫入權限，
     * 明確排除 users 表，確保本機排程器無法存取帳號資料。
     * 這是最小權限原則的實踐：排程器只需查訂閱、寫歷史。
     */
    const schedulerPolicy = new iam.ManagedPolicy(this, 'SchedulerPolicy', {
      managedPolicyName: 'yt-to-mail-scheduler-policy',
      description: 'yt-to-mail local scheduler: read subscriptions, write history only',
      statements: [
        new iam.PolicyStatement({
          sid: 'ReadSubscriptions',
          effect: iam.Effect.ALLOW,
          actions: [
            'dynamodb:Query',
            'dynamodb:GetItem',
            'dynamodb:Scan',
            'dynamodb:UpdateItem',   // 自動取消：累加/重置 no_new_video_days 計數器
            'dynamodb:DeleteItem',   // 自動取消：刪除已達取消條件的訂閱
          ],
          resources: [
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-subscriptions`,
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-subscriptions/index/*`,
          ],
        }),
        new iam.PolicyStatement({
          sid: 'WriteReadHistory',
          effect: iam.Effect.ALLOW,
          actions: [
            'dynamodb:PutItem',
            'dynamodb:Scan',
            'dynamodb:Query',   // 查詢已寄送影片清單（get_sent_video_ids 透過 user_id-index GSI）
          ],
          resources: [
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-history`,
            `arn:aws:dynamodb:${this.region}:${this.account}:table/yt-to-mail-history/index/*`,
          ],
        }),
      ],
    });

    /**
     * 本機排程器 IAM User
     * 建立專用 IAM User 並附加最小權限 Policy，
     * 使用 Access Key 讓本機 Python 腳本可透過 AWS CLI 存取 DynamoDB，
     * 不使用 Lambda Role 以明確區分雲端執行與本機執行的憑證邊界。
     */
    const schedulerUser = new iam.User(this, 'SchedulerUser', {
      userName: 'yt-to-mail-scheduler',
      managedPolicies: [schedulerPolicy],
    });

    /**
     * 本機排程器 IAM Access Key
     * 使用 CfnAccessKey 產生 Access Key ID 與 Secret Access Key，
     * 輸出至 CfnOutput 供本機 aws configure 設定使用。
     * 注意：Secret Access Key 只在建立時可見，務必妥善保存。
     */
    const schedulerAccessKey = new iam.CfnAccessKey(this, 'SchedulerAccessKey', {
      userName: schedulerUser.userName,
    });

    new cdk.CfnOutput(this, 'SchedulerAccessKeyId', {
      value: schedulerAccessKey.ref,
      description: 'yt-to-mail-scheduler IAM User Access Key ID',
      exportName: 'YtToMailSchedulerAccessKeyId',
    });

    new cdk.CfnOutput(this, 'SchedulerSecretAccessKey', {
      value: schedulerAccessKey.attrSecretAccessKey,
      description: 'yt-to-mail-scheduler IAM User Secret Access Key (store securely)',
      exportName: 'YtToMailSchedulerSecretAccessKey',
    });
  }
}
