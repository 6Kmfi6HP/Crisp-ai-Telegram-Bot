#!/bin/sh

# conver_to_array(){
#     local BOT_SEND_ID_env=$1
#     local IFS=","
#     str=""
#     for send_id in ${BOT_SEND_ID_env};do
#         str="$str    - ${send_id}\n"
#     done
#     result=`echo -e "${str}"`
# }
AUTOREPLY=`echo -e "${AUTOREPLY}"`
OPENAI_PAYLOAD=`echo -e "${OPENAI_PAYLOAD}"`

# 检查配置文件是否存在，如果存在则跳过环境变量配置
if [ ! -e "/Crisp-Telegram-Bot/config.yml" ]; then
    echo "配置文件不存在，使用环境变量生成配置文件..."
    cat > /Crisp-Telegram-Bot/config.yml << EOF
bot:
  token: ${BOT_TOKEN}
  groupId: ${BOT_GROUPID}
crisp:
  id: ${CRISP_ID}
  key: ${CRISP_KEY}
  website: ${CRISP_WEBSITE}
easyimages:
  apiUrl: ${EasyImages_apiUrl}
  apiToken: ${EasyImages_apiToken}

cloudflare_r2:
  endpoint_url: "${CLOUDFLARE_R2_ENDPOINT_URL}"
  access_key_id: "${CLOUDFLARE_R2_ACCESS_KEY_ID}"
  secret_access_key: "${CLOUDFLARE_R2_SECRET_ACCESS_KEY}"
  bucket_name: "${CLOUDFLARE_R2_BUCKET_NAME}"
  public_url: "${CLOUDFLARE_R2_PUBLIC_URL}"
autoreply:
${AUTOREPLY}
openai:
  apiKey: ${OPENAI_APIKEY}
  baseUrl: ${OPENAI_BASEURL:-"https://api.openai.com/v1"}
  model: ${OPENAI_MODEL:-"gpt-3.5-turbo"}
  payload: |
${OPENAI_PAYLOAD}

# 数据持久化配置
persistence:
  storage_type: "${PERSISTENCE_STORAGE_TYPE:-sqlite}"
  data_file: "${PERSISTENCE_DATA_FILE:-data/session_data.db}"
  expire_days: ${PERSISTENCE_EXPIRE_DAYS:-14}
  async_save:
    enabled: ${PERSISTENCE_ASYNC_SAVE_ENABLED:-true}
    batch_interval: ${PERSISTENCE_BATCH_INTERVAL:-30}
    max_batch_size: ${PERSISTENCE_MAX_BATCH_SIZE:-100}
  auto_cleanup:
    enabled: ${PERSISTENCE_AUTO_CLEANUP_ENABLED:-true}
    check_interval: ${PERSISTENCE_CHECK_INTERVAL:-6}
EOF
else
    echo "配置文件已存在，忽略环境变量配置"
fi
exec "$@"