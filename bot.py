
import os
import yaml
import logging
import requests
import boto3
from botocore.exceptions import ClientError
from io import BytesIO

from openai import OpenAI
from crisp_api import Crisp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, Defaults, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import handler

# 定期清理过期会话的任务函数
async def cleanup_expired_sessions(context: ContextTypes.DEFAULT_TYPE):
    """定期清理过期的会话数据"""
    try:
        # 清理持久化存储中的过期数据
        handler.persistence.clean_expired_data()
        
        # 清理内存中的过期数据
        if hasattr(context, 'bot_data'):
            # 重新加载有效数据到内存
            valid_data = handler.persistence.load_session_data()
            context.bot_data.clear()
            context.bot_data.update(valid_data)
            
        # 获取统计信息
        stats = handler.persistence.get_stats()
        logging.info(f"数据清理完成 - 当前活跃会话: {stats['total_sessions']}, 待保存: {stats['pending_saves']}")
        
    except Exception as e:
        logging.error(f"清理过期数据时发生错误: {e}")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

# Load Config
try:
    f = open('config.yml', 'r')
    config = yaml.safe_load(f)
except FileNotFoundError as error:
    logging.warning('没有找到 config.yml，请复制 config.yml.example 并重命名为 config.yml')
    exit(1)

# Connect Crisp
try:
    crispCfg = config['crisp']
    client = Crisp()
    client.set_tier("plugin")
    client.authenticate(crispCfg['id'], crispCfg['key'])
    client.plugin.get_connect_account()
    client.website.get_website(crispCfg['website'])
except Exception as error:
    logging.warning('无法连接 Crisp 服务，请确认 Crisp 配置项是否正确')
    exit(1)

# Connect OpenAI
try:
    openai_config = config['openai']
    openai = OpenAI(
        api_key=openai_config['apiKey'],
        base_url=openai_config.get('baseUrl', 'https://api.openai.com/v1')
    )
    # Test connection
    openai.models.list()
    logging.info('OpenAI 服务连接成功')
except Exception as error:
    logging.warning('无法连接 OpenAI 服务，智能化回复将不会使用: ' + str(error))
    openai = None

def changeButton(sessionId,boolean):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(
                text='关闭 AI 回复' if boolean else '打开 AI 回复',
                callback_data=f'{sessionId},{boolean}'
                )
            ]
        ]
    )

async def onReply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message

    if msg.chat_id != config['bot']['groupId']:
        return
    for sessionId in context.bot_data:
        if context.bot_data[sessionId]['topicId'] == msg.message_thread_id:
            query = {
                "type": "text",
                "content": msg.text,
                "from": "operator",
                "origin": "chat",
                "user": {
                    "nickname": '人工客服',
                    "avatar": 'https://bpic.51yuansu.com/pic3/cover/03/47/92/65e3b3b1eb909_800.jpg'
                }
            }
            client.website.send_message_in_conversation(
                config['crisp']['website'],
                sessionId,
                query
            )
            return

# EasyImages Config
EASYIMAGES_API_URL = config.get('easyimages', {}).get('apiUrl', '')
EASYIMAGES_API_TOKEN = config.get('easyimages', {}).get('apiToken', '')

# Cloudflare R2 Config
R2_CONFIG = config.get('cloudflare_r2', {})
R2_ENDPOINT_URL = R2_CONFIG.get('endpoint_url', '')
R2_ACCESS_KEY_ID = R2_CONFIG.get('access_key_id', '')
R2_SECRET_ACCESS_KEY = R2_CONFIG.get('secret_access_key', '')
R2_BUCKET_NAME = R2_CONFIG.get('bucket_name', '')
R2_PUBLIC_URL = R2_CONFIG.get('public_url', '')

# 初始化 R2 客户端
r2_client = None
if R2_ENDPOINT_URL and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME:
    try:
        r2_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name='auto'  # R2 使用 'auto' 作为区域
        )
        logging.info('Cloudflare R2 客户端初始化成功')
    except Exception as e:
        logging.warning(f'Cloudflare R2 客户端初始化失败: {e}')
        r2_client = None
else:
    logging.info('Cloudflare R2 配置不完整，将仅使用 EasyImages')

async def handleImage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document and msg.document.mime_type.startswith('image/'):
        file_id = msg.document.file_id
    else:
        await msg.reply_text("请发送图片文件。")
        return

    try:
        # 获取文件下载 URL
        file = await context.bot.get_file(file_id)
        file_url = file.file_path

        # 上传图片（优先 R2，失败时回退到 EasyImages）
        uploaded_url = upload_image_with_fallback(file_url)

        # 生成 Markdown 格式的链接
        markdown_link = f"![Image]({uploaded_url})"

        # 查找对应的 Crisp 会话 ID
        session_id = get_target_session_id(context, msg.message_thread_id)
        if session_id:
            # 将 Markdown 链接推送给客户
            send_markdown_to_client(session_id, markdown_link)
            await msg.reply_text("图片已成功发送给客户！")
        else:
            await msg.reply_text("未找到对应的 Crisp 会话，无法发送给客户。")

    except Exception as e:
        await msg.reply_text("图片上传失败，请稍后重试。")
        logging.error(f"图片上传错误: {e}")

def upload_image_to_easyimages(file_url):
    try:
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        files = {
            'image': ('image.jpg', response.raw, 'image/jpeg'),
            'token': (None, EASYIMAGES_API_TOKEN)
        }
        res = requests.post(EASYIMAGES_API_URL, files=files)
        res_data = res.json()

        if res_data.get("result") == "success":
            return res_data["url"]
        else:
            raise Exception(f"Image upload failed: {res_data}")
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        raise

def upload_image_to_r2(file_url):
    """上传图片到 Cloudflare R2"""
    try:
        if not r2_client:
            raise Exception("R2 客户端未初始化")
        
        # 下载图片
        response = requests.get(file_url)
        response.raise_for_status()
        
        # 生成唯一的文件名
        import uuid
        import mimetypes
        
        # 从 URL 获取文件扩展名，确保使用正确的图片格式
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        # 手动映射常见的图片MIME类型到扩展名
        mime_to_ext = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg', 
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/bmp': '.bmp',
            'image/tiff': '.tiff',
            'image/svg+xml': '.svg'
        }
        
        extension = mime_to_ext.get(content_type.lower())
        if not extension:
            # 如果MIME类型不在映射中，尝试使用mimetypes库
            extension = mimetypes.guess_extension(content_type)
            # 如果还是无法获取或者是.bin，默认使用.png
            if not extension or extension == '.bin':
                extension = '.png'
        
        filename = f"{uuid.uuid4().hex}{extension}"
        
        # 上传到 R2
        r2_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=filename,
            Body=BytesIO(response.content),
            ContentType=content_type
        )
        
        # 构建公共 URL
        if R2_PUBLIC_URL:
            # 使用自定义域名或 r2.dev URL
            public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{filename}"
        else:
            # 如果没有配置公共 URL，返回 R2 的默认 URL 格式
            public_url = f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{filename}"
        
        logging.info(f"图片已成功上传到 R2: {public_url}")
        return public_url
        
    except ClientError as e:
        logging.error(f"R2 上传失败: {e}")
        raise
    except Exception as e:
        logging.error(f"R2 上传错误: {e}")
        raise

def upload_image_with_fallback(file_url):
    """优先使用 R2 上传，失败时回退到 EasyImages"""
    # 优先尝试 R2
    if r2_client:
        try:
            return upload_image_to_r2(file_url)
        except Exception as e:
            logging.warning(f"R2 上传失败，回退到 EasyImages: {e}")
    
    # 回退到 EasyImages
    if EASYIMAGES_API_URL and EASYIMAGES_API_TOKEN:
        try:
            return upload_image_to_easyimages(file_url)
        except Exception as e:
            logging.error(f"EasyImages 上传也失败: {e}")
            raise
    else:
        raise Exception("没有可用的图片上传服务")

def get_target_session_id(context, thread_id):
    for session_id, session_data in context.bot_data.items():
        if session_data.get('topicId') == thread_id:
            return session_id
    return None

def send_markdown_to_client(session_id, markdown_link):
    try:
        # 将 Markdown 图片链接作为纯文本发送
        query = {
            "type": "text",
            "content": markdown_link,  # 将图片链接当做普通文本
            "from": "operator",
            "origin": "chat",
            "user": {
                "nickname": "人工客服",
                "avatar": "https://bpic.51yuansu.com/pic3/cover/03/47/92/65e3b3b1eb909_800.jpg"
            }
        }
        client.website.send_message_in_conversation(
            config['crisp']['website'],
            session_id,
            query
        )
        logging.info(f"图片链接已成功发送至 Crisp 会话 {session_id}")
    except Exception as e:
        logging.error(f"发送图片链接到 Crisp 失败: {e}")
        raise

async def onChange(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    if openai is None:
        await query.answer('无法设置此功能')
    else:
        data = query.data.split(',')
        session = context.bot_data.get(data[0])
        session["enableAI"] = not eval(data[1])
        await query.answer()
        try:
             await query.edit_message_reply_markup(changeButton(data[0],session["enableAI"]))
        except Exception as error:
            print(error)

def main():
    try:
        app = Application.builder().token(config['bot']['token']).defaults(Defaults(parse_mode='HTML')).build()
        
        # 加载持久化的会话数据
        try:
            persistent_data = handler.persistence.load_session_data()
            app.bot_data.update(persistent_data)
            logging.info(f"加载了 {len(persistent_data)} 个持久化会话")
        except Exception as e:
            logging.error(f"加载持久化数据失败: {e}")
        
        # 启动 Bot
        if os.getenv('RUNNER_NAME') is not None:
            return
            
        app.add_handler(MessageHandler(filters.TEXT, onReply))
        app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handleImage))
        app.add_handler(CallbackQueryHandler(onChange))
        app.job_queue.run_once(handler.exec,5,name='RTM')
        
        # 设置定期清理过期数据的任务
        cleanup_config = config.get('persistence', {}).get('auto_cleanup', {})
        if cleanup_config.get('enabled', True):
            check_interval_hours = cleanup_config.get('check_interval', 6)
            app.job_queue.run_repeating(
                cleanup_expired_sessions,
                interval=check_interval_hours * 3600,  # 转换为秒
                first=300,  # 5分钟后开始第一次清理
                name='cleanup_expired_sessions'
            )
            logging.info(f"已设置每 {check_interval_hours} 小时清理一次过期数据")
        
        # 设置程序退出时强制保存待保存的数据
        import atexit
        atexit.register(lambda: handler.persistence.force_save_pending())
        
        app.run_polling(drop_pending_updates=True)
    except Exception as error:
        logging.warning('无法启动 Telegram Bot，请确认 Bot Token 是否正确，或者是否能连接 Telegram 服务器')
        exit(1)


if __name__ == "__main__":
    main()
