# 数据持久化功能说明

本项目已集成数据持久化功能，支持会话数据的本地存储和自动清理，解决了机器人重启后数据丢失的问题。

## 功能特性

### 1. 多种存储方式
- **SQLite数据库**：推荐用于生产环境，性能更好，支持并发访问
- **JSON文件**：适合开发环境或小规模部署

### 2. 异步保存机制
- 批量保存：避免频繁I/O操作影响性能
- 可配置的保存间隔和批量大小
- 程序退出时自动保存所有待保存数据

### 3. 自动过期清理
- 可配置的数据过期时间（默认14天）
- 定期自动清理过期数据
- 启动时自动清理过期数据

### 4. 数据恢复
- 机器人重启时自动加载有效的会话数据
- 保持Crisp会话与Telegram线程的对应关系

## 配置说明

在 `config.yml` 中添加以下配置：

```yaml
# 数据持久化配置
persistence:
  # 存储类型: json 或 sqlite
  storage_type: "sqlite"
  # 数据文件路径
  data_file: "session_data.db"
  # 会话过期时间（天）
  expire_days: 14
  # 异步保存配置
  async_save:
    # 是否启用异步保存
    enabled: true
    # 批量保存间隔（秒）
    batch_interval: 30
    # 最大批量大小
    max_batch_size: 100
  # 自动清理配置
  auto_cleanup:
    # 是否启用自动清理
    enabled: true
    # 清理检查间隔（小时）
    check_interval: 6
```

### 配置项详解

#### storage_type
- `sqlite`：使用SQLite数据库存储（推荐）
- `json`：使用JSON文件存储

#### data_file
- SQLite模式：数据库文件路径（如：`session_data.db`）
- JSON模式：JSON文件路径（如：`session_data.json`）

#### expire_days
- 会话数据的过期时间，单位为天
- 超过此时间的会话将被自动清理

#### async_save
- `enabled`：是否启用异步保存机制
- `batch_interval`：批量保存的时间间隔（秒）
- `max_batch_size`：单次批量保存的最大数据条数

#### auto_cleanup
- `enabled`：是否启用自动清理功能
- `check_interval`：清理检查的时间间隔（小时）

## 使用建议

### 生产环境推荐配置
```yaml
persistence:
  storage_type: "sqlite"
  data_file: "session_data.db"
  expire_days: 30
  async_save:
    enabled: true
    batch_interval: 60
    max_batch_size: 200
  auto_cleanup:
    enabled: true
    check_interval: 12
```

### 开发环境推荐配置
```yaml
persistence:
  storage_type: "json"
  data_file: "session_data.json"
  expire_days: 7
  async_save:
    enabled: false
  auto_cleanup:
    enabled: true
    check_interval: 1
```

## 数据结构

### SQLite表结构
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    topic_id INTEGER,
    message_id INTEGER,
    enable_ai BOOLEAN,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### JSON数据结构
```json
{
  "session_id_1": {
    "topicId": 123,
    "messageId": 456,
    "enableAI": true,
    "last_updated": "2024-01-01T12:00:00"
  }
}
```

## 性能优化

### 1. 异步保存
- 启用异步保存可以显著减少I/O阻塞
- 适当调整 `batch_interval` 和 `max_batch_size` 以平衡性能和数据安全

### 2. 存储选择
- **小规模部署**（<1000会话）：JSON文件足够
- **中大规模部署**（>1000会话）：建议使用SQLite
- **高并发环境**：考虑升级到PostgreSQL或MySQL

### 3. 清理策略
- 根据业务需求调整 `expire_days`
- 在低峰时段进行清理（调整 `check_interval`）

## 监控和维护

### 日志信息
系统会记录以下关键信息：
- 启动时加载的会话数量
- 定期清理的数据统计
- 异步保存的执行情况
- 错误和异常信息

### 数据备份
建议定期备份数据文件：
- SQLite：备份 `.db` 文件
- JSON：备份 `.json` 文件

### 故障恢复
如果数据文件损坏：
1. 停止机器人
2. 恢复备份文件
3. 重启机器人

## 升级路径

### 从内存存储升级
1. 更新配置文件添加 `persistence` 配置
2. 重启机器人（首次启动会创建空的持久化存储）
3. 新的会话将自动持久化

### 从JSON升级到SQLite
1. 修改配置 `storage_type: "sqlite"`
2. 重启机器人（系统会自动迁移数据）

## 故障排除

### 常见问题

1. **数据库文件权限错误**
   - 确保机器人进程有读写权限
   - 检查文件路径是否正确

2. **JSON文件格式错误**
   - 检查JSON文件语法
   - 删除损坏的文件让系统重新创建

3. **内存占用过高**
   - 减少 `max_batch_size`
   - 增加清理频率
   - 减少 `expire_days`

4. **性能问题**
   - 启用异步保存
   - 考虑升级到SQLite
   - 调整批量保存参数

### 调试模式
在配置中临时禁用异步保存以便调试：
```yaml
persistence:
  async_save:
    enabled: false
```

这样可以立即看到保存操作的结果和错误信息。