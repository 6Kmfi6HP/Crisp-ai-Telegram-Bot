# Cloudflare R2 图片上传配置指南

本项目现在支持使用 Cloudflare R2 作为图片上传的主要服务，EasyImages 作为备选方案。

## 功能特性

- **智能回退机制**: 优先使用 Cloudflare R2 上传，失败时自动回退到 EasyImages
- **自定义域名支持**: 支持使用自定义域名或 r2.dev 开发域名
- **安全配置**: 支持通过环境变量配置敏感信息
- **高可用性**: 双重上传服务确保图片上传的可靠性

## 配置步骤

### 1. 创建 Cloudflare R2 存储桶

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. 进入 **R2 Object Storage**
3. 点击 **Create bucket** 创建新的存储桶
4. 记录存储桶名称

### 2. 获取 API 凭证

1. 在 Cloudflare Dashboard 中，进入 **My Profile** > **API Tokens**
2. 点击 **Create Token**
3. 选择 **R2 Token** 模板
4. 配置权限：
   - **Account**: 选择你的账户
   - **Zone Resources**: Include - All zones
   - **Account Resources**: Include - All accounts
5. 创建后记录 **Access Key ID** 和 **Secret Access Key**

### 3. 配置公共访问（可选）

#### 方式一：使用 r2.dev 开发域名
1. 在存储桶设置中，启用 **Public Development URL**
2. 记录生成的 r2.dev URL

#### 方式二：使用自定义域名（推荐）
1. 确保你的域名已添加到 Cloudflare
2. 在存储桶设置中，添加 **Custom Domain**
3. 配置 DNS 记录（Cloudflare 会自动处理）
4. 等待域名状态变为 **Active**

### 4. 更新配置文件

编辑 `config.yml` 文件，添加以下配置：

```yaml
cloudflare_r2:
  endpoint_url: "https://your-account-id.r2.cloudflarestorage.com"
  access_key_id: "your_r2_access_key_id"
  secret_access_key: "your_r2_secret_access_key"
  bucket_name: "your-bucket-name"
  public_url: "https://your-custom-domain.com"  # 或 https://pub-xxxxx.r2.dev
```

**配置说明：**
- `endpoint_url`: R2 API 端点，格式为 `https://your-account-id.r2.cloudflarestorage.com`
- `access_key_id`: R2 访问密钥 ID
- `secret_access_key`: R2 秘密访问密钥
- `bucket_name`: 存储桶名称
- `public_url`: 公共访问 URL（自定义域名或 r2.dev URL）

### 5. 环境变量配置（可选，更安全）

为了提高安全性，你可以使用环境变量来配置敏感信息：

```bash
# Windows
set AWS_ACCESS_KEY_ID=your_r2_access_key_id
set AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key

# Linux/macOS
export AWS_ACCESS_KEY_ID=your_r2_access_key_id
export AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key
```

如果设置了环境变量，可以在 `config.yml` 中省略 `access_key_id` 和 `secret_access_key`。

## 使用说明

1. **自动回退**: 系统会优先尝试使用 Cloudflare R2 上传图片，如果失败会自动回退到 EasyImages
2. **日志监控**: 查看应用日志可以了解当前使用的上传服务和任何错误信息
3. **配置验证**: 启动时会验证 R2 配置，如果配置不完整会提示并仅使用 EasyImages

## 故障排除

### 常见问题

1. **R2 客户端初始化失败**
   - 检查 `endpoint_url` 格式是否正确
   - 验证 API 凭证是否有效
   - 确认账户 ID 是否正确

2. **上传失败**
   - 检查存储桶名称是否正确
   - 验证 API 凭证权限
   - 查看详细错误日志

3. **图片无法访问**
   - 确认存储桶已启用公共访问
   - 检查 `public_url` 配置是否正确
   - 验证自定义域名状态是否为 Active

### 兼容性说明

- **boto3 版本**: 推荐使用 1.35.99，避免使用 1.36.0（存在已知兼容性问题）
- **Python 版本**: 支持 Python 3.7+

## 最佳实践

1. **使用自定义域名**: 相比 r2.dev，自定义域名提供更好的性能和功能
2. **配置 CDN**: 利用 Cloudflare 的 CDN 功能加速图片访问
3. **监控使用量**: 定期检查 R2 使用量和费用
4. **备份策略**: 虽然有 EasyImages 作为备选，建议定期备份重要图片
5. **安全配置**: 使用环境变量存储敏感信息，避免在代码中硬编码

## 费用说明

Cloudflare R2 的定价模式：
- **存储**: $0.015/GB/月
- **Class A 操作** (写入): $4.50/百万次请求
- **Class B 操作** (读取): $0.36/百万次请求
- **出站流量**: 免费（这是 R2 的主要优势）

相比其他云存储服务，R2 在出站流量方面有显著的成本优势。