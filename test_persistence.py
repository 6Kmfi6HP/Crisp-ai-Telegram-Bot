import yaml
from persistence import SessionPersistence

# 加载配置
with open('config.yml', 'r') as f:
    config = yaml.safe_load(f)

# 初始化持久化管理器
persistence = SessionPersistence(config)

# 测试加载数据
print("=== 测试数据加载 ===")
loaded_data = persistence.load_session_data()
print(f"加载的数据: {loaded_data}")
print(f"数据条数: {len(loaded_data)}")

# 测试保存数据
print("\n=== 测试数据保存 ===")
test_session_id = "test_session_123"
test_data = {
    'topicId': 999,
    'messageId': 888,
    'enableAI': True
}

persistence.save_session_data(test_session_id, test_data)
print(f"保存测试数据: {test_session_id} -> {test_data}")

# 强制保存待保存的数据
persistence.force_save_pending()

# 重新加载验证
print("\n=== 验证保存结果 ===")
reloaded_data = persistence.load_session_data()
print(f"重新加载的数据: {reloaded_data}")
print(f"测试数据是否存在: {test_session_id in reloaded_data}")

# 获取统计信息
print("\n=== 统计信息 ===")
stats = persistence.get_stats()
for key, value in stats.items():
    print(f"{key}: {value}")