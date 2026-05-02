/**
 * YtToMailFrontendStack
 *
 * 建立 yt-to-mail 系統的前端靜態網站部署基礎設施：
 * - S3 Bucket：封鎖公開存取，僅允許 CloudFront OAC 讀取
 * - CloudFront OAC（Origin Access Control）：取代舊版 OAI，使用 sigv4 簽署
 * - CloudFront Distribution：強制 HTTPS、分層快取、SPA 路由錯誤處理
 * - BucketDeployment：自動上傳 frontend/dist/ 至 S3 並觸發 CloudFront Invalidation
 *
 * 採用 OAC 而非 OAI 的原因：
 * OAC 是 AWS 目前推薦的 S3 存取控制機制，支援 SSE-KMS 加密物件，
 * 且安全性更高（支援請求簽署驗證），舊版 OAI 已被 AWS 標記為 legacy。
 *
 * L2 Distribution + OAC 整合說明：
 * CDK L2 的 Distribution 目前尚未原生支援 OAC，
 * 因此需在 L2 建立後，透過 addPropertyOverride 手動設定 OAC ID，
 * 同時清除 L2 自動產生的空白 OAI 設定。
 */
import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';
import { Construct } from 'constructs';

export class YtToMailFrontendStack extends cdk.Stack {
  /**
   * CloudFront Distribution 供外部取得網域名稱使用
   */
  public readonly distribution: cloudfront.Distribution;

  /**
   * S3 Bucket 供外部取得 Bucket 名稱使用
   */
  public readonly bucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================
    // Step 1：建立 S3 Bucket（封鎖公開存取，RemovalPolicy.DESTROY）
    // =========================================================

    /**
     * 前端靜態檔案 S3 Bucket
     * 封鎖所有公開存取，僅透過 CloudFront OAC 提供服務，
     * 原型階段使用 DESTROY + autoDeleteObjects 方便清理資源。
     * 不啟用靜態網站代管（Static Website Hosting），
     * 因為使用 CloudFront + OAC 時不需要此功能，且啟用後無法使用 OAC。
     */
    this.bucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `yt-to-mail-frontend-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // =========================================================
    // Step 2：建立 CloudFront OAC（L1 Construct）
    // =========================================================

    /**
     * CloudFront Origin Access Control（OAC）
     * 使用 L1 CfnOriginAccessControl，因為 CDK L2 尚未提供對應的 Construct。
     * signingBehavior: 'always' 確保所有請求都帶有 SigV4 簽署，
     * 防止未經授權的直接 S3 存取。
     */
    const oac = new cloudfront.CfnOriginAccessControl(this, 'FrontendOAC', {
      originAccessControlConfig: {
        name: 'yt-to-mail-frontend-oac',
        originAccessControlOriginType: 's3',
        signingBehavior: 'always',
        signingProtocol: 'sigv4',
        description: 'OAC for yt-to-mail frontend S3 bucket',
      },
    });

    // =========================================================
    // Step 3：建立 CloudFront Distribution（L2）
    // =========================================================

    /**
     * CloudFront Distribution
     * 使用 S3BucketOrigin 建立基本 Origin，之後再手動覆寫 OAC 設定。
     * defaultBehavior 採用 CachingOptimized 策略（靜態資源長期快取）。
     * additionalBehaviors 為 *.html 路徑套用 CachingDisabled（不快取，TTL=0）。
     * errorResponses 將 403/404 重導至 index.html，支援 React SPA 路由。
     */
    this.distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(this.bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
        compress: true,
      },
      additionalBehaviors: {
        '*.html': {
          origin: origins.S3BucketOrigin.withOriginAccessControl(this.bucket),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
          compress: true,
        },
      },
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
      httpVersion: cloudfront.HttpVersion.HTTP2,
      defaultRootObject: 'index.html',
      comment: 'yt-to-mail frontend CloudFront Distribution',
    });

    // =========================================================
    // Step 4：手動覆寫 L1 cfnDistribution 的 OAC 設定
    // =========================================================

    /**
     * 手動覆寫 cfnDistribution 的 OAC 相關屬性
     * CDK L2 的 S3BucketOrigin.withOriginAccessControl() 會自動處理 OAC，
     * 但我們使用手動建立的 CfnOriginAccessControl，
     * 需要確認 Origin[0] 使用正確的 OAC ID。
     * 同時清除任何殘留的 OriginAccessIdentity（OAI）設定，
     * 確保僅使用 OAC 存取 S3，避免舊版 OAI 影響。
     */
    const cfnDistribution = this.distribution.node.defaultChild as cloudfront.CfnDistribution;
    cfnDistribution.addPropertyOverride(
      'DistributionConfig.Origins.0.OriginAccessControlId',
      oac.attrId
    );
    cfnDistribution.addPropertyOverride(
      'DistributionConfig.Origins.0.S3OriginConfig.OriginAccessIdentity',
      ''
    );
    // additionalBehaviors 的 *.html 也有 Origin（index 1），同樣覆寫
    cfnDistribution.addPropertyOverride(
      'DistributionConfig.Origins.1.OriginAccessControlId',
      oac.attrId
    );
    cfnDistribution.addPropertyOverride(
      'DistributionConfig.Origins.1.S3OriginConfig.OriginAccessIdentity',
      ''
    );

    // =========================================================
    // Step 5：設定 S3 Bucket Policy（允許 CloudFront OAC 讀取）
    // =========================================================

    /**
     * S3 Bucket Policy：允許 CloudFront 服務主體讀取物件
     * 條件限制 aws:SourceArn 為本 Distribution ARN，
     * 確保只有此 CloudFront Distribution 可存取 S3，
     * 防止其他 CloudFront Distribution 繞過存取控制。
     */
    this.bucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: 'AllowCloudFrontServicePrincipal',
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
        actions: ['s3:GetObject'],
        resources: [this.bucket.arnForObjects('*')],
        conditions: {
          StringEquals: {
            'aws:SourceArn': `arn:aws:cloudfront::${this.account}:distribution/${this.distribution.distributionId}`,
          },
        },
      })
    );

    // =========================================================
    // Step 6：BucketDeployment 上傳前端靜態檔案並觸發 CloudFront Invalidation
    // =========================================================

    /**
     * BucketDeployment：自動上傳 frontend/dist/ 至 S3
     * 指定 distribution 與 distributionPaths 後，CDK 部署完成時
     * 會自動觸發 CloudFront Invalidation，確保用戶取得最新版本。
     * 無需手動執行 aws s3 sync 或 aws cloudfront create-invalidation。
     */
    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../frontend/dist'))],
      destinationBucket: this.bucket,
      distribution: this.distribution,
      distributionPaths: ['/*'],
    });

    // =========================================================
    // Step 7：CfnOutput 輸出關鍵資訊
    // =========================================================

    /**
     * 輸出 CloudFront 網域名稱（不含 https://）
     * 供設定 Lambda Function URL CORS AllowOrigins 使用
     */
    new cdk.CfnOutput(this, 'CloudFrontDomain', {
      value: this.distribution.distributionDomainName,
      description: 'CloudFront 網域名稱（不含 https://）',
      exportName: 'YtToMailCloudFrontDomain',
    });

    /**
     * 輸出完整前端 URL（含 https://）
     * 供瀏覽器直接存取使用
     */
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: '完整前端 URL（https:// 開頭）',
      exportName: 'YtToMailCloudFrontUrl',
    });

    /**
     * 輸出 S3 Bucket 名稱
     * 供 AWS CLI 上傳靜態檔案使用
     */
    new cdk.CfnOutput(this, 'S3BucketName', {
      value: this.bucket.bucketName,
      description: 'S3 Bucket 名稱（供 CLI 上傳靜態檔案使用）',
      exportName: 'YtToMailS3BucketName',
    });

    /**
     * 輸出 CloudFront Distribution ID
     * 供執行 CloudFront Invalidation（清除快取）使用
     */
    new cdk.CfnOutput(this, 'CloudFrontDistributionId', {
      value: this.distribution.distributionId,
      description: 'CloudFront Distribution ID（供 Invalidation 使用）',
      exportName: 'YtToMailCloudFrontDistributionId',
    });
  }
}
