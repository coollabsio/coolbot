import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
SUPPORT_CHANNEL_ID = int(os.getenv('SUPPORT_CHANNEL_ID'))

STARTUP_LOG_THREAD_ID = int(os.getenv('STARTUP_LOG_THREAD_ID'))
POST_CREATE_LOG_THREAD_ID = int(os.getenv('POST_CREATE_LOG_THREAD_ID'))

AUTHORIZED_ROLE_ID = int(os.getenv('AUTHORIZED_ROLE_ID'))

COOLIFY_CLOUD_TAG_ID = int(os.getenv('COOLIFY_CLOUD_TAG_ID'))
SOLVED_TAG_ID = int(os.getenv('SOLVED_TAG_ID'))
NOT_SOLVED_TAG_ID = int(os.getenv('NOT_SOLVED_TAG_ID'))
NEED_DEV_REVIEW_TAG_ID = int(os.getenv('NEED_DEV_REVIEW_TAG_ID'))
UNANSWERED_TAG_ID = int(os.getenv('UNANSWERED_TAG_ID'))
WAITING_FOR_REPLY_TAG_ID = int(os.getenv('WAITING_FOR_REPLY_TAG_ID'))

COMMUNITY_SUPPORT_CHANNEL_ID = int(os.getenv('COMMUNITY_SUPPORT_CHANNEL_ID'))
COMMUNITY_SOLVED_TAG_ID = int(os.getenv('COMMUNITY_SOLVED_TAG_ID'))
PRIVATE_DATA_THREAD_ID = int(os.getenv('PRIVATE_DATA_THREAD_ID'))
COOLBOT_ADMIN_ROLE_ID = int(os.getenv('COOLBOT_ADMIN_ROLE_ID'))
DEV_SUPPORT_STATION_CHANNEL_ID = int(os.getenv('DEV_SUPPORT_STATION_CHANNEL_ID'))
CLOUD_SUPPORT_ALERT_ROLE_ID = int(os.getenv('CLOUD_SUPPORT_ALERT_ROLE_ID'))
CORE_DEVELOPER_SUPPORT_ALERT_ROLE_ID = int(os.getenv('CORE_DEVELOPER_SUPPORT_ALERT_ROLE_ID'))

# Page actions logging
PAGE_ACTIONS_THREAD_ID = int(os.getenv('PAGE_ACTIONS_THREAD_ID'))

# Page response webhook
PAGE_RESPONSE_WEBHOOK_URL = os.getenv('PAGE_RESPONSE_WEBHOOK_URL')

# NTFY configuration for /page alerts
NTFY_TOPIC_NAME = os.getenv('NTFY_TOPIC_NAME')
NTFY_SECOND_TOPIC = os.getenv('NTFY_SECOND_TOPIC')

# Contributor role configuration
CONTRIBUTORS_CHANNEL_ID = int(os.getenv('CONTRIBUTORS_CHANNEL_ID'))
CONTRIBUTOR_ROLE_ID = int(os.getenv('CONTRIBUTOR_ROLE_ID'))
GITHUB_REPOS = os.getenv('GITHUB_REPOS', '').split(',')  # Comma-separated list of repos like 'coollabsio/coolify,coollabsio/documentation'