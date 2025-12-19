import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import aiohttp, json, os, asyncio, random, datetime
from typing import Literal, Optional, Union

from config import (
    PAGE_ACTIONS_THREAD_ID,
    PAGE_RESPONSE_WEBHOOK_URL,
    AUTHORIZED_ROLE_ID,
    COOLBOT_ADMIN_ROLE_ID,
    NTFY_TOPIC_NAME,
    NTFY_SECOND_TOPIC
)

def generate_random_id():
    """Generate a random alphanumeric ID for websocket tracking"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join(random.choice(chars) for _ in range(8))

class PageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recent_page = None  # Store recent page info for rate limiting
        self.page_websockets: dict[str, asyncio.Task] = {}  # id: task

    async def send_page_log(self, user: Union[discord.User, discord.Member], title: str, description: str, priority: int, page_id: str):
        """Send log message to the page actions thread"""
        log_channel = self.bot.get_channel(PAGE_ACTIONS_THREAD_ID)
        if not log_channel or not (isinstance(log_channel, discord.TextChannel) or isinstance(log_channel, discord.Thread)):
            return

        # Create simple text log message
        log_message = f" `{user.name}` used **/page**. Title: `{title}` | Description: `{description}` | Priority: `{priority}` | ID: `{page_id}`"

        try:
            await log_channel.send(log_message)
        except Exception as e:
            print(f"Failed to send page log: {e}")

    async def send_simple_log(self, message: str):
        """Send a simple text log message to the page actions thread"""
        log_channel = self.bot.get_channel(PAGE_ACTIONS_THREAD_ID)
        if log_channel and (isinstance(log_channel, discord.TextChannel) or isinstance(log_channel, discord.Thread)):
            try:
                await log_channel.send(message)
            except Exception as e:
                print(f"Failed to send simple log: {e}")

    async def handle_websocket(self, followup: discord.Message, random_id: str):
        """Handle websocket connections for page responses"""
        if not NTFY_SECOND_TOPIC:
            return
        try:
            await self.send_simple_log(f"Attempting to connect to WS with ID: `{random_id}`")
            async with aiohttp.ClientSession(trust_env=True) as cs:
                async with cs.ws_connect(f"wss://ntfy.sh/{str(NTFY_SECOND_TOPIC)}/ws") as ws:
                    await self.send_simple_log(f"WS connected to ID: `{random_id}`")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self.send_simple_log(f"WS event received `Type: TEXT | ID: `{random_id}`")
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            await self.send_simple_log(f"WS event received `Type: ERROR | ID: `{random_id}`")
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            await self.send_simple_log(f"WS event received `Type: CLOSED | ID: `{random_id}`")
                        else:
                            await self.send_simple_log(f"WS event received `Type: {msg.type} | ID: `{random_id}`")

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = msg.json()
                                if "message" in data and data["message"] == random_id:
                                    title = data.get("title", "")
                                    if title in ["On it", "Soon (Next 30 mins)", "Later (> 1 hour)"]:
                                        # Send webhook notification if configured
                                        if PAGE_RESPONSE_WEBHOOK_URL:
                                            async with aiohttp.ClientSession() as webhook_session:
                                                webhook_data = {
                                                    "content": f"{title}\n-# Reply to {followup.jump_url}"
                                                }
                                                try:
                                                    async with webhook_session.post(PAGE_RESPONSE_WEBHOOK_URL, json=webhook_data) as resp:
                                                        if resp.status != 204:
                                                            print(f"Webhook failed with status {resp.status}")
                                                except Exception as e:
                                                    print(f"Webhook error: {e}")

                                        # Log the response
                                        await self.send_simple_log(f"Page response received: `{title}`")

                                        if random_id in self.page_websockets:
                                            self.page_websockets[random_id].cancel()
                                            del self.page_websockets[random_id]
                                        break
                            except json.JSONDecodeError:
                                continue
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            if random_id in self.page_websockets:
                del self.page_websockets[random_id]

    async def send_page(self, title: str, message: str, priority: int, followup: discord.Message, user: Optional[discord.Member] = None):
        """Send notification to ntfy.sh with page details"""
        severity_emojis = {
            1: "green_circle",  # information
            2: "yellow_circle",  # Minor
            3: "orange_circle",  # Major
            4: "red_circle"   # Critical - Critical
        }
        tags = [severity_emojis.get(priority, "question")]
        if not user:  # automated page
            tags.append("robot")  # 🤖

        async with aiohttp.ClientSession(trust_env=True) as cs:
            random_id = generate_random_id()
            if self.recent_page:
                self.recent_page["id"] = random_id
            data = {
                "topic": NTFY_TOPIC_NAME,
                "message": message,
                "title": title,
                "tags": tags,
                "click": followup.jump_url,
                "actions": [
                    {
                        "action": "http",
                        "label": "On it",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC or 'default'}",
                        "headers": {"Title": "On it", "message": random_id},
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Soon (Next 30mins)",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC or 'default'}",
                        "headers": {"Title": "Soon (Next 30 mins)", "message": random_id},
                        "clear": True
                    },
                    {
                        "action": "http",
                        "label": "Later (>1 hour)",
                        "url": f"https://ntfy.sh/{NTFY_SECOND_TOPIC or 'default'}",
                        "headers": {"Title": "Later (> 1 hour)", "message": random_id},
                        "clear": True
                    }
                ] if NTFY_SECOND_TOPIC else []
            }
            if priority == 4:
                data["priority"] = 5
            if user and hasattr(user, 'display_avatar'):
                data["icon"] = user.display_avatar.url

            try:
                async with cs.post("https://ntfy.sh/", data=json.dumps(data)) as req:
                    if req.status == 200:
                        if user:
                            await self.send_page_log(user, title.split(' | ')[0], message, priority, random_id)
                            await followup.edit(content=f"Notification sent successfully.\n-# Title: `{title.split(' | ')[0]}` | Description: `{message}` | Priority: `{priority}` |  ID: `{random_id}`")
                        else:
                            await followup.edit(content=f"Automated page sent successfully.\n-# Priority: {priority} | ID: `{random_id}`")
                            # For automated pages, we don't have user/title/description, so skip logging
                        task = asyncio.create_task(self.handle_websocket(followup, random_id))
                        self.page_websockets[random_id] = task
                    else:
                        response = await req.text()
                        await followup.edit(content=f"An error occurred while sending the notification...\nStatus: {req.status}, Response: {response}")
            except Exception as e:
                await followup.edit(content=f"An error occurred while sending the notification... {e}")
                raise e

    @app_commands.command(name="page", description="Alert the developer of any downtime or critical issues")
    @app_commands.checks.has_any_role(AUTHORIZED_ROLE_ID, COOLBOT_ADMIN_ROLE_ID)
    @app_commands.describe(
        title="The title of the page alert",
        description="The description/message to send",
        priority="The severity, 1 = lowest, 4 = critical (highest)"
    )
    async def page(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        priority: Literal["4 | Critical", "3 | Major issue", "2 | Minor issue", "1 | Information"]
    ):
        priority_dict = {
            "4 | Critical": 4,
            "3 | Major issue": 3,
            "2 | Minor issue": 2,
            "1 | Information": 1
        }

        priority_num = priority_dict[priority]

        fifteen_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=15)

        if self.recent_page and datetime.datetime.fromtimestamp(self.recent_page["timestamp"]) > fifteen_minutes_ago:
            await interaction.response.defer(ephemeral=True)
            button = ui.Button(style=discord.ButtonStyle.danger, label="Confirm", custom_id="page-confirm")

            async def callback(interaction: discord.Interaction):
                # Defer the response to avoid timeout
                await interaction.response.defer()

                # Delete the original confirmation message
                try:
                    await interaction.delete_original_response()
                except:
                    pass  # Ignore if already deleted

                # Send the page as a new message in the channel
                if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
                    followup = await interaction.channel.send("Sending...")
                    self.recent_page = {
                        "user_id": interaction.user.id,
                        "message": description,
                        "timestamp": round(datetime.datetime.now().timestamp()),
                        "priority": priority_num,
                        "service": title
                    }
                    user_member = interaction.user if isinstance(interaction.user, discord.Member) else None
                    await self.send_page(f"{title} | Sent by @{interaction.user.name}", description, priority_num, followup, user_member)

            button.callback = callback
            view = ui.View()
            view.add_item(button)

            embed = discord.Embed(
                title="⚠️ Hold up!",
                description="A page was recently sent with similar details.",
                color=0xffa500  # Orange color for warning
            )
            if self.recent_page:
                embed.add_field(
                    name="Previous Page",
                    value=f"Sent <t:{self.recent_page['timestamp']}:R> by <@{self.recent_page['user_id']}>",
                    inline=False
                )
                embed.add_field(
                    name="Title",
                    value=f"`{self.recent_page['service']}`",
                    inline=True
                )
                embed.add_field(
                    name="Priority",
                    value=f"`{self.recent_page['priority']}`",
                    inline=True
                )
                embed.add_field(
                    name="Description",
                    value=f"```{self.recent_page['message'][:100]}{'...' if len(self.recent_page['message']) > 100 else ''}```",
                    inline=False
                )
            embed.set_footer(text="Click confirm to send anyway, or dismiss to cancel")

            await interaction.followup.send(embed=embed, ephemeral=True, view=view)
        else:
            await interaction.response.defer()
            followup = await interaction.followup.send("Sending...", wait=True)
            self.recent_page = {
                "user_id": interaction.user.id,
                "message": description,
                "timestamp": round(datetime.datetime.now().timestamp()),
                "priority": priority_num,
                "service": title
            }
            user_member = interaction.user if isinstance(interaction.user, discord.Member) else None
            await self.send_page(f"{title} | Sent by @{interaction.user.name}", description, priority_num, followup, user_member)

    @app_commands.command(name="page-ws-close", description="Manually close a websocket created after a /page")
    @app_commands.checks.has_any_role(AUTHORIZED_ROLE_ID, COOLBOT_ADMIN_ROLE_ID)
    async def page_websockets_close(self, interaction: discord.Interaction, id: Optional[str] = None):
        if self.page_websockets:
            if id:
                if id in self.page_websockets.keys():
                    self.page_websockets[id].cancel()
                    del self.page_websockets[id]
                    await self.send_simple_log(f"{interaction.user.mention} closed page websocket with id `{id}`")
                    await interaction.response.send_message(f"Closed websocket with ID `{id}`", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        f"Invalid key provided. Received `{id}`. Available keys: `{', '.join([key for key in self.page_websockets.keys()]) or 'None'}`",
                        ephemeral=True
                    )
            else:
                button = ui.Button(style=discord.ButtonStyle.danger, label="Confirm", custom_id="page_websocket_close_confirm")

                async def callback(interaction: discord.Interaction):
                    keys = list(self.page_websockets.keys())
                    for key in keys:
                        self.page_websockets[key].cancel()
                        del self.page_websockets[key]
                    await self.send_simple_log(f"{interaction.user.mention} closed all page websockets")
                    await interaction.response.send_message("Closed all active page websockets", ephemeral=True)

                button.callback = callback
                view = ui.View()
                view.add_item(button)
                await interaction.response.send_message(
                    "Are you sure you would like to close all currently open page websockets?\n"
                    "**This action can't be undone**",
                    view=view,
                    ephemeral=True
                )
        else:
            await interaction.response.send_message("No active page websockets to close", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PageCog(bot))