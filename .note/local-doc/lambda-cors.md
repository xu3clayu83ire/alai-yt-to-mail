## allowedOrigin 的用途
Lambda Function URL 有 CORS 設定（跨來源資源共用）。瀏覽器的安全規則要求 API 只能接受來自「已知網域」的請求。

階段	allowedOrigin	說明
初次部署	*（萬用）	還不知道 CloudFront 網域
Phase 4 後	https://drtl6k13ydgdp.cloudfront.net	限制只有前端網站可以呼叫 API


## 只部署後端（並設定 CORS）
npx cdk deploy YtToMailBackendStack --context allowedOrigin=https://xxx.cloudfront.net