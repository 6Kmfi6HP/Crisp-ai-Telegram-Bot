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

# if [ ! -e "/Crisp-Telegram-Bot/config.yml" ]; then
# conver_to_array ${BOT_SEND_ID}
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
# fi
exec "$@"