
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
            response = openai.chat.completions.create(
                model=config['openai'].get('model', 'gpt-3.5-turbo'),
                messages=[
                    {"role": "system", "content": payload},
                    {"role": "user", "content": data["content"]}
                ]
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