
import bot
import json
import base64
import socketio
import requests
from telegram.ext import ContextTypes
from persistence import SessionPersistence

config = bot.config
client = bot.client
openai = bot.openai
changeButton = bot.changeButton
groupId = config["bot"]["groupId"]
websiteId = config["crisp"]["website"]
payload = config["openai"]["payload"]

# 初始化持久化管理器
persistence = SessionPersistence(config)

def getKey(content: str):
    if len(config["autoreply"]) > 0:
        for x in config["autoreply"]:
            keyword = x.split("|")
            for key in keyword:
                if key in content:
                    return True, config["autoreply"][x]
    return False, None

def getMetas(sessionId):
    metas = client.website.get_conversation_metas(websiteId, sessionId)

    flow = ['📠<b>Crisp消息推送</b>','']
    
    # 基本用户信息
    if len(metas.get("nickname", "")) > 0:
        nickname = metas["nickname"]
        flow.append(f'👤<b>用户昵称</b>：{nickname}')
    
    if len(metas.get("email", "")) > 0:
        email = metas["email"]
        flow.append(f'📧<b>电子邮箱</b>：{email}')
    
    if len(metas.get("phone", "")) > 0:
        phone = metas["phone"]
        flow.append(f'📱<b>电话号码</b>：{phone}')
    
    # 地理位置和网络信息
    if len(metas.get("data", {})) > 0:
        data = metas["data"]
        
        # 地理位置信息
        if "Country" in data:
            country = data["Country"]
            flow.append(f"🌍<b>国家地区</b>：{country}")
        
        if "City" in data:
            city = data["City"]
            flow.append(f"🏙<b>城市</b>：{city}")
        
        if "Full_Address" in data:
            address = data["Full_Address"]
            flow.append(f"📍<b>详细地址</b>：{address}")
        
        if "IP_Address" in data:
            ip = data["IP_Address"]
            flow.append(f"🌐<b>IP地址</b>：{ip}")
        
        if "ISP_Name" in data:
            isp = data["ISP_Name"]
            flow.append(f"📡<b>网络服务商</b>：{isp}")
        
        if "Trust_Score" in data:
            trust_score = data["Trust_Score"]
            flow.append(f"🛡<b>信任评分</b>：{trust_score}")
        
        # 设备和浏览器信息
        if "Operating_System" in data:
            os = data["Operating_System"]
            flow.append(f"💻<b>操作系统</b>：{os}")
        
        if "Browser" in data:
            browser = data["Browser"]
            flow.append(f"🌐<b>浏览器</b>：{browser}")
        
        if "Device_Type" in data:
            device_type = data["Device_Type"]
            flow.append(f"📱<b>设备类型</b>：{device_type}")
        
        if "Screen_Resolution" in data:
            resolution = data["Screen_Resolution"]
            flow.append(f"🖥<b>屏幕分辨率</b>：{resolution}")
        
        # 时间和时区信息
        if "Timezone" in data:
            timezone = data["Timezone"]
            flow.append(f"🕐<b>时区</b>：{timezone}")
        
        if "Local_Time" in data:
            local_time = data["Local_Time"]
            flow.append(f"⏰<b>本地时间</b>：{local_time}")
        
        if "Registration_Date" in data:
            reg_date = data["Registration_Date"]
            flow.append(f"📅<b>注册日期</b>：{reg_date}")
        
        if "Session_Start" in data:
            session_start = data["Session_Start"]
            flow.append(f"🚀<b>会话开始</b>：{session_start}")
        
        # 用户相关信息
        if "User_Role" in data:
            user_role = data["User_Role"]
            flow.append(f"👔<b>用户角色</b>：{user_role}")
        
        if "Wallet_Balance" in data:
            balance = data["Wallet_Balance"]
            flow.append(f"💰<b>钱包余额</b>：{balance}")
        
        # 原有的套餐和流量信息
        if "Plan" in data:
            Plan = data["Plan"]
            flow.append(f"🪪<b>使用套餐</b>：{Plan}")
        
        if "UsedTraffic" in data and "AllTraffic" in data:
            UsedTraffic = data["UsedTraffic"]
            AllTraffic = data["AllTraffic"]
            flow.append(f"🗒<b>流量信息</b>：{UsedTraffic} / {AllTraffic}")
        
        # 页面访问信息
        if "Current_Page" in data:
            current_page = data["Current_Page"]
            flow.append(f"📄<b>当前页面</b>：{current_page}")
        
        if "Referrer_Page" in data:
            referrer = data["Referrer_Page"]
            flow.append(f"🔗<b>来源页面</b>：{referrer}")
        
        if "Browser_Language" in data:
            language = data["Browser_Language"]
            flow.append(f"🌐<b>浏览器语言</b>：{language}")
    
    if len(flow) > 2:
        return '\n'.join(flow)
    return '无额外信息'


async def createSession(data):
    bot = callbackContext.bot
    botData = callbackContext.bot_data
    sessionId = data["session_id"]
    session = botData.get(sessionId)
    
    # 如果内存中没有会话数据，尝试从持久化存储加载
    if session is None:
        try:
            persistent_data = persistence.load_session_data()
            if sessionId in persistent_data:
                session = persistent_data[sessionId]
                botData[sessionId] = session
                print(f"从持久化存储恢复会话: {sessionId}")
        except Exception as e:
            print(f"加载持久化会话数据失败: {e}")

    metas = getMetas(sessionId)
    if session is None:
        enableAI = False if openai is None else True
        topic = await bot.create_forum_topic(
            groupId,data["user"]["nickname"])
        msg = await bot.send_message(
            groupId,
            metas,
            message_thread_id=topic.message_thread_id,
            reply_markup=changeButton(sessionId,enableAI)
            )
        session_data = {
            'topicId': topic.message_thread_id,
            'messageId': msg.message_id,
            'enableAI': enableAI
        }
        botData[sessionId] = session_data
        
        # 持久化保存会话数据
        persistence.save_session_data(sessionId, session_data)
        print(f"创建新会话: {sessionId}")
    else:
        try:
            await bot.edit_message_text(metas,groupId,session['messageId'])
            # 更新会话的最后活动时间
            persistence.save_session_data(sessionId, session)
            print(f"更新现有会话: {sessionId}")
        except Exception as error:
            print(error)

async def sendMessage(data):
    bot = callbackContext.bot
    botData = callbackContext.bot_data
    sessionId = data["session_id"]
    session = botData.get(sessionId)

    client.website.mark_messages_read_in_conversation(websiteId,sessionId,
        {"from": "user", "origin": "chat", "fingerprints": [data["fingerprint"]]}
    )

    if data["type"] == "text":
        flow = ['📠<b>消息推送</b>','']
        flow.append(f"🧾<b>消息内容</b>：{data['content']}")

        result, autoreply = getKey(data["content"])
        if result is True:
            flow.append("")
            flow.append(f"💡<b>自动回复</b>：{autoreply}")
        elif openai is not None and session["enableAI"] is True:
            # 获取历史消息作为上下文
            try:
                import tiktoken
                
                model_name = config['openai'].get('model', 'gpt-3.5-turbo')
                # 获取对应模型的编码器
                try:
                    encoding = tiktoken.encoding_for_model(model_name)
                except KeyError:
                    encoding = tiktoken.get_encoding("cl100k_base")  # 默认编码器
                
                # 设置token限制（为响应预留空间）
                max_tokens = 4096 if 'gpt-3.5-turbo' in model_name else 8192
                max_context_tokens = max_tokens - 1000  # 为响应预留1000个token
                
                history_response = client.website.get_messages_in_conversation(websiteId, sessionId, {})
                messages = [{"role": "system", "content": payload}]
                
                # 计算系统消息的token数
                current_tokens = len(encoding.encode(payload)) + 4  # 4个额外token用于消息格式
                
                print(f"历史消息API响应类型: {type(history_response)}, 长度: {len(history_response) if isinstance(history_response, list) else 'N/A'}")
                
                # 处理历史消息
                history_messages = []
                # Crisp API直接返回消息数组，不是包含data字段的对象
                if isinstance(history_response, list) and history_response:
                    print(f"获取到历史消息数量: {len(history_response)}")
                    
                    # 过滤并排序历史消息（排除当前消息）
                    valid_messages = []
                    current_content = data["content"].strip()
                    
                    for msg in history_response:
                        if (msg.get('type') == 'text' and 
                            'content' in msg and 
                            msg['content'].strip() and 
                            msg['content'].strip() != current_content):  # 排除当前消息
                            valid_messages.append(msg)
                    
                    print(f"有效历史消息数量: {len(valid_messages)}")
                    
                    # 按时间顺序处理消息（从最新开始，但插入时保持正确顺序）
                    for msg in reversed(valid_messages[-20:]):  # 最多取最近20条
                        role = "assistant" if msg.get('from') == 'operator' else "user"
                        content = msg['content'].strip()
                        
                        # 计算这条消息的token数
                        msg_tokens = len(encoding.encode(content)) + 4
                        
                        # 检查是否超过token限制
                        if current_tokens + msg_tokens > max_context_tokens:
                            print(f"Token限制达到，停止添加历史消息")
                            break
                        
                        history_messages.insert(0, {"role": role, "content": content})
                        current_tokens += msg_tokens
                        print(f"添加历史消息: {role} - {content[:50]}...")
                    
                    messages.extend(history_messages)
                else:
                    print("没有获取到历史消息数据或数据格式不正确")
                
                # 添加当前用户消息
                current_msg_tokens = len(encoding.encode(data["content"])) + 4
                if current_tokens + current_msg_tokens <= max_context_tokens:
                    messages.append({"role": "user", "content": data["content"]})
                else:
                    # 如果当前消息太长，截断历史消息
                    while len(messages) > 1 and current_tokens + current_msg_tokens > max_context_tokens:
                        removed_msg = messages.pop(1)  # 保留系统消息，移除最早的历史消息
                        current_tokens -= len(encoding.encode(removed_msg["content"])) + 4
                    messages.append({"role": "user", "content": data["content"]})
                
                print(f"发送给OpenAI的消息数量: {len(messages)}, 预估token数: {current_tokens + current_msg_tokens}")
                
                response = openai.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=min(300, max_tokens - current_tokens - current_msg_tokens),  # 客服AI使用较短回复
                    temperature=0.7
                )
                autoreply = response.choices[0].message.content
                
            except ImportError:
                print("tiktoken未安装，使用简化的历史消息处理")
                # 如果tiktoken未安装，使用简化版本
                history_response = client.website.get_messages_in_conversation(websiteId, sessionId, {})
                messages = [{"role": "system", "content": payload}]
                
                if 'data' in history_response:
                    recent_messages = history_response['data'][-5:]  # 只保留最近5条消息
                    for msg in recent_messages:
                        if msg.get('type') == 'text' and 'content' in msg and msg['content'].strip():
                            role = "assistant" if msg.get('from') == 'operator' else "user"
                            messages.append({"role": role, "content": msg['content'].strip()})
                
                messages.append({"role": "user", "content": data["content"]})
                
                response = openai.chat.completions.create(
                    model=config['openai'].get('model', 'gpt-3.5-turbo'),
                    messages=messages,
                    max_tokens=300,  # 客服AI使用较短回复
                    temperature=0.7
                )
                autoreply = response.choices[0].message.content
                
            except Exception as e:
                print(f"获取历史消息失败，使用无上下文模式: {e}")
                # 如果获取历史消息失败，回退到原来的无上下文模式
                response = openai.chat.completions.create(
                    model=config['openai'].get('model', 'gpt-3.5-turbo'),
                    messages=[
                        {"role": "system", "content": payload},
                        {"role": "user", "content": data["content"]}
                    ],
                    max_tokens=300,  # 客服AI使用较短回复
                    temperature=0.7
                )
                autoreply = response.choices[0].message.content
            flow.append("")
            flow.append(f"💡<b>自动回复</b>：{autoreply}")
        
        if autoreply is not None:
            query = {
                "type": "text",
                "content": autoreply,
                "from": "operator",
                "origin": "chat",
                "user": {
                    "nickname": '智能客服',
                    "avatar": 'https://img.ixintu.com/download/jpg/20210125/8bff784c4e309db867d43785efde1daf_512_512.jpg'
                }
            }
            client.website.send_message_in_conversation(websiteId, sessionId, query)
        await bot.send_message(
            groupId,
            '\n'.join(flow),
            message_thread_id=session["topicId"]
        )
    elif data["type"] == "file" and str(data["content"]["type"]).count("image") > 0:
        await bot.send_photo(
            groupId,
            data["content"]["url"],
            message_thread_id=session["topicId"]
        )
    else:
        print("Unhandled Message Type : ", data["type"])

sio = socketio.AsyncClient(reconnection_attempts=5, logger=True)
# Def Event Handlers
@sio.on("connect")
async def connect():
    await sio.emit("authentication", {
        "tier": "plugin",
        "username": config["crisp"]["id"],
        "password": config["crisp"]["key"],
        "events": [
            "message:send",
            "session:set_data"
        ]})
@sio.on("unauthorized")
async def unauthorized(data):
    print('Unauthorized: ', data)
@sio.event
async def connect_error():
    print("The connection failed!")
@sio.event
async def disconnect():
    print("Disconnected from server.")
@sio.on("message:send")
async def messageForward(data):
    if data["website_id"] != websiteId:
        return
    await createSession(data)
    await sendMessage(data)

# Meow!
def getCrispConnectEndpoints():
    url = "https://api.crisp.chat/v1/plugin/connect/endpoints"

    authtier = base64.b64encode(
        (config["crisp"]["id"] + ":" + config["crisp"]["key"]).encode("utf-8")
    ).decode("utf-8")
    payload = ""
    headers = {"X-Crisp-Tier": "plugin", "Authorization": "Basic " + authtier}
    response = requests.request("GET", url, headers=headers, data=payload)
    endPoint = json.loads(response.text).get("data").get("socket").get("app")
    return endPoint

# Connecting to Crisp RTM(WSS) Server
async def exec(context: ContextTypes.DEFAULT_TYPE):
    global callbackContext
    callbackContext = context
    # await sendAllUnread()
    await sio.connect(
        getCrispConnectEndpoints(),
        transports="websocket",
        wait_timeout=10,
    )
    await sio.wait()