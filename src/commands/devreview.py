import discord
from discord.ext import commands
from discord import app_commands
import logging

from config import (
    NEED_DEV_REVIEW_TAG_ID,
    TEAM_THREAD_CHANNEL_ID,
    AUTHORIZED_ROLE_ID,
    TEAM_ALERT_ROLE_ID,
    COOLIFY_CLOUD_TAG_ID
)

logger = logging.getLogger(__name__)

async def process_immediate_alert(post: discord.Thread, staff: discord.Member, bot: commands.Bot, additional_info: str = None):
    """
    Sends an embed with details (and any additional info) to the designated team channel,
    updates the forum post's tags, and notifies the post.
    """
    team_channel = bot.get_channel(TEAM_THREAD_CHANNEL_ID)
    if team_channel is None:
        return

    # Retrieve current tag IDs regardless of type.
    current_tags_raw = post.applied_tags if post.applied_tags else []
    current_tag_ids = []
    for tag in current_tags_raw:
        if isinstance(tag, int):
            current_tag_ids.append(tag)
        else:
            current_tag_ids.append(tag.id)

    if COOLIFY_CLOUD_TAG_ID in current_tag_ids:
        new_tags = [discord.Object(id=COOLIFY_CLOUD_TAG_ID), discord.Object(id=NEED_DEV_REVIEW_TAG_ID)]
        is_coolify_cloud = True
    else:
        new_tags = [discord.Object(id=NEED_DEV_REVIEW_TAG_ID)]
        is_coolify_cloud = False

    try:
        await post.edit(applied_tags=new_tags)
    except Exception as e:
        pass

    # Build the embed description with exact markdown list formatting.
    basic_info_lines = [
        "**__Basic Information__**",
        "- Link to the post",
        f"  - {post.jump_url}",
        "- User Type",
        f"  - {'Coolify Cloud User' if is_coolify_cloud else 'Self Host User'}",
        "** **"
    ]

    user_info_lines = []
    if additional_info:
        user_info_lines.append("**__Information from User__**")
        # Mapping from form keys to expected display labels.
        field_mapping = {
            "Email": "Email Address",
            "Issue Start Time": "When did this issue Started?",
            "Deployed Apps Accessible?": "Are your deployed apps accessible?",
            "Urgency": "How soon do you need a fix?",
            "Actions that led to the issue": "What actions led to this issue?"
        }
        # Process each line from the modal response.
        for line in additional_info.splitlines():
            # Remove markdown formatting characters.
            clean_line = line.replace("**", "").replace("`", "").strip()
            if not clean_line:
                continue
            if ": " in clean_line:
                key, value = clean_line.split(": ", 1)
                key = key.strip()
                value = value.strip()
                mapped_key = field_mapping.get(key, key)
                user_info_lines.append(f"- {mapped_key}")
                user_info_lines.append(f"  - {value}")
            else:
                user_info_lines.append(clean_line)

    # Combine basic and user info sections.
    description_lines = basic_info_lines + user_info_lines
    new_description = "\n".join(description_lines)

    # Set the embed color to #9c7eff and update the footer with the staff's display name.
    embed = discord.Embed(
        description=new_description,
        color=discord.Color(int("9c7eff", 16))
    )
    embed.set_footer(text=f"Invoked by {staff.display_name}")

    try:
        await team_channel.send(content=f"Hey <@&{TEAM_ALERT_ROLE_ID}> a support post needs your attention!", embed=embed)
    except Exception as e:
        pass

    try:
        notify_embed = discord.Embed(
            description=f"{staff.mention} has escalated this post for review by the core team. \n\n"
                        f"A team member will assist you as soon as possible. \n\n"
                        f"You will be pinged once you receive a response and please avoid pinging anyone in the meantime.",
            color=discord.Color.green() 
        )
        
        await post.send(embed=notify_embed)
            
    except Exception as e:
        logger.error(f"Failed to send dev review notification: {e}")

class UserSelectView(discord.ui.View):
    """
    A view that displays a user select element so the staff can choose the user
    who needs to provide additional info.
    The select options are built from the provided list of thread members.
    """
    def __init__(self, post: discord.Thread, staff: discord.Member, bot: commands.Bot, members: list):
        super().__init__(timeout=60)
        self.post = post
        self.staff = staff
        self.bot = bot
        options = []
        if members:
            for m in members:
                full_member = self.post.guild.get_member(m.id) or m
                label = getattr(full_member, "display_name", str(full_member))
                options.append(discord.SelectOption(label=label, value=str(m.id)))
        else:
            options = [
                discord.SelectOption(
                    label="No members available",
                    value="none",
                    default=True,
                    description="No members are following this post."
                )
            ]
        self.select = discord.ui.Select(
            placeholder="Select a user",
            min_values=1,
            max_values=1,
            options=options
        )
        self.select.callback = self.user_select_callback
        self.add_item(self.select)

    async def user_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            selected_value = self.select.values[0]
            if (selected_value == "none"):
                await interaction.followup.send("No valid members available to select.", ephemeral=True)
                return
            selected_user_id = int(selected_value)
            selected_user = self.post.guild.get_member(selected_user_id)
        except Exception as e:
            error_embed = discord.Embed(description="Failed to select user.", color=discord.Color.red())
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return
        try:
            view = SubmitInfoView(self.post, selected_user, self.staff, self.bot, None)
            notify_embed = discord.Embed(
                description=f"{self.staff.mention} needs more details before escalating this post to the core team. \n\n"
                            f"Please click the button below.",
                color=discord.Color.blue()
            )
            ping_msg = await self.post.send(content=f"Hey {selected_user.mention}!", embed=notify_embed, view=view)
            view.message_to_delete = ping_msg
            
            # Save the submit info view to database
            try:
                await self.bot.db.add_view(
                    message_id=ping_msg.id,
                    channel_id=self.post.parent_id,
                    thread_id=self.post.id,
                    view_type='submit_info',
                    post_owner_id=selected_user.id
                )
            except Exception as e:
                logger.error(f"Failed to save submit info view to database: {e}")
        except Exception as e:
            logger.error(f"Failed to create submit info view: {e}")
        try:
            await interaction.delete_original_response()
        except Exception as e:
            pass
        self.stop()

class SubmitInfoView(discord.ui.View):
    """
    A view with a button labeled "Submit information" that, when clicked by the designated user,
    shows a modal for them to enter additional details.
    """
    def __init__(self, post: discord.Thread, target_user: discord.Member, staff: discord.Member, bot: commands.Bot, message_to_delete: discord.Message):
        super().__init__(timeout=None) 
        self.post = post
        self.target_user = target_user
        self.staff = staff
        self.bot = bot
        self.message_to_delete = message_to_delete

    @discord.ui.button(
        label="Submit Information", 
        style=discord.ButtonStyle.primary,
        custom_id="submit_info_button" 
    )
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_user.id:
            error_embed = discord.Embed(description="This option is unavailable to you. Only the staff-picked member can use it.", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        try:
            modal = RequestMoreInfoModal(self.post, self.staff, self.bot, self.message_to_delete)
            await interaction.response.send_modal(modal)
        except Exception as e:
            pass

class RequestMoreInfoModal(discord.ui.Modal, title="coolLabs Support"):
    """
    A modal presented to the selected user to collect additional information.
    The modal now covers:
      1. Email
      2. Error Messages? & When did the issue start?
      3. Are your deployed apps accessible?
      4. Urgency: How soon do you need a fix?
      5. What action did you take before encountering this issue? + Additional details
    """
    def __init__(self, post: discord.Thread, staff: discord.Member, bot: commands.Bot, message_to_delete: discord.Message):
        super().__init__()
        self.post = post
        self.staff = staff
        self.bot = bot
        self.message_to_delete = message_to_delete

        self.email = discord.ui.TextInput(
            label="Email",
            style=discord.TextStyle.short,
            placeholder="Enter your Coolify cloud account email",
            required=True
        )
        self.issue_start_time = discord.ui.TextInput(
            label="When did this issue Started?",
            style=discord.TextStyle.short,
            placeholder="Example: Feb 29th at 5:22pm GMT+1",
            required=True
        )
        self.apps_accessible = discord.ui.TextInput(
            label="Are your deployed apps accessible?",
            style=discord.TextStyle.short,
            placeholder="Example: Yes",
            required=True
        )
        self.urgency = discord.ui.TextInput(
            label="How soon do you need a fix?",
            style=discord.TextStyle.short,
            placeholder="Example: Tomorrow is okay.",
            required=True
        )
        self.action_details = discord.ui.TextInput(
            label="What actions led to this issue?",
            style=discord.TextStyle.long,
            placeholder="Example: I changed the proxy labels for Traefik.",
            required=True
        )

        self.add_item(self.email)
        self.add_item(self.issue_start_time)
        self.add_item(self.apps_accessible)
        self.add_item(self.urgency)
        self.add_item(self.action_details)

    async def on_submit(self, interaction: discord.Interaction):
        email_value = self.email.value
        issue_start_time_value = self.issue_start_time.value
        apps_accessible_value = self.apps_accessible.value
        urgency_value = self.urgency.value
        action_details_value = self.action_details.value

        additional_info = (
            f"**Email:** `{email_value}`\n"
            f"**Issue Start Time:** `{issue_start_time_value}`\n"
            f"**Deployed Apps Accessible?:** `{apps_accessible_value}`\n"
            f"**Urgency:** `{urgency_value}`\n"
            f"**Actions that led to the issue:** `{action_details_value}`"
        )
        try:
            await process_immediate_alert(self.post, self.staff, self.bot, additional_info)
        except Exception as e:
            pass
        try:
            thank_embed = discord.Embed(
                description="Thank you. Your information has been submitted to the core team.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=thank_embed, ephemeral=True)
        except Exception as e:
            pass
        # Delete the ping message after modal submission.
        try:
            if self.message_to_delete:
                await self.message_to_delete.delete()
        except Exception as e:
            pass


class MarkReviewView(discord.ui.View):
    """
    A view with two buttons:
      • "Alert the dev and add tag" – Immediately sends the alert and clears the ephemeral message.
      • "Request user for more info and automate alert" – Edits the message to ask the executor to choose the user.
    """
    def __init__(self, post: discord.Thread, staff: discord.Member, bot: commands.Bot):
        super().__init__(timeout=180) 
        self.post = post
        self.staff = staff
        self.bot = bot

    @discord.ui.button(
        label="Alert the developer and add the tag", 
        style=discord.ButtonStyle.primary,
        custom_id="alert_dev"
    )
    async def alert_dev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception as e:
            pass
            
        try:
            await process_immediate_alert(self.post, self.staff, self.bot)
        except Exception as e:
            pass
            
        try:
            await interaction.delete_original_response()
        except Exception as e:
            pass

        # When resolved, remove the view from database
        try:
            message = await self.post.fetch_message(interaction.message.id)
            await self.bot.db.remove_view(message.id)
        except Exception as e:
            logger.error(f"Failed to remove view from database: {e}")
            pass

    @discord.ui.button(
        label="Request details from user and auto-send alert", 
        style=discord.ButtonStyle.secondary,
        custom_id="request_info"
    )
    async def request_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed = discord.Embed(description="Please select the user to request more info:", color=discord.Color.blue())
            try:
                members = await self.post.fetch_members()
            except Exception as e:
                members = []
            view = UserSelectView(self.post, self.staff, self.bot, members=members)
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            pass
        self.stop()

class NeedDevReviewCog(commands.Cog):
    """
    Main cog that provides the /needs-dev-review command to initiate the workflow.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="needs-dev-review", description="Mark this post as needs developer review")
    async def mark_as_need_dev_review(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.Thread):
            error_embed = discord.Embed(description="This command can only be used in the support forum channel.", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        post = interaction.channel
        if AUTHORIZED_ROLE_ID not in [role.id for role in interaction.user.roles]:
            error_embed = discord.Embed(description="You do not have permission to use this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        current_tags = post.applied_tags if post.applied_tags else []
        current_tag_ids = []
        for tag in current_tags:
            if isinstance(tag, int):
                current_tag_ids.append(tag)
            else:
                current_tag_ids.append(tag.id)
        if NEED_DEV_REVIEW_TAG_ID in current_tag_ids:
            warning_embed = discord.Embed(description="This post is already marked as need dev review.", color=discord.Color.orange())
            await interaction.response.send_message(embed=warning_embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="Mark as Needs Developer Review",
            description="Click one of the buttons below to choose how you'd like to proceed.",
            color=discord.Color.blue()
        )
        view = MarkReviewView(post, interaction.user, self.bot)
        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(NeedDevReviewCog(bot))
