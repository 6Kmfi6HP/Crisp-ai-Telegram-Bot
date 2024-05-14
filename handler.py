
import bot
import json
import base64
import socketio
import requests
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

config = bot.config
client = bot.client
groupId = config["bot"]["groupId"]
websiteId = config["crisp"]["website"]

def getMetas(sessionId):
    metas = client.website.get_conversation_metas(websiteId, sessionId)

    flow = ['📠<b>Crisp消息推送</b>','']
    if len(metas["email"]) > 0:
        email = metas["email"]
        flow.append(f'📧<b>电子邮箱</b>：{email}')
    if len(metas["data"]) > 0:
        if "Plan" in metas["data"]:
            Plan = metas["data"]["Plan"]
            flow.append(f"🪪<b>使用套餐</b>：{Plan}")
        if "UsedTraffic" in metas["data"] and "AllTraffic" in metas["data"]:
            UsedTraffic = metas["data"]["UsedTraffic"]
            AllTraffic = metas["data"]["AllTraffic"]
            flow.append(f"🗒<b>流量信息</b>：{UsedTraffic} / {AllTraffic}")
    if len(flow) > 2:
        return '\n'.join(flow)
    return '无额外信息'

async def createSession(data):
    bot = callbackContext.bot
    botData = callbackContext.bot_data
    sessionId = data["session_id"]
    session = botData.get(sessionId)

    metas = getMetas(sessionId)
    if session is None:
        topic = await bot.create_forum_topic(
            groupId,data["user"]["nickname"])
        msg = await bot.send_message(
            groupId,
            metas,
            message_thread_id=topic.message_thread_id
            )
        botData[sessionId] = {
            'topicId': topic.message_thread_id,
            'messageId': msg.message_id,
        }
    else:
        await bot.edit_message_text('加载中',groupId,session['messageId'])
        await bot.edit_message_text(metas,groupId,session['messageId'])

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