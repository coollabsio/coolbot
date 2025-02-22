import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))

STARTUP_LOG_THREAD_ID = int(os.getenv('STARTUP_LOG_THREAD_ID'))
POST_CREATE_LOG_THREAD_ID = int(os.getenv('POST_CREATE_LOG_THREAD_ID'))

AUTHORIZED_ROLE_ID = int(os.getenv('AUTHORIZED_ROLE_ID'))
