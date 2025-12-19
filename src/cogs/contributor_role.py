import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, button, Button, Modal, TextInput
import aiohttp
import asyncio
import secrets
import string
from typing import List

# Repository configuration - repos under organization
# Format: orgname/reponame
REPOSITORIES = [
    "coollabsio/coolify",
    "coollabsio/coolify-docs",
    "coollabsio/coolify-cli",
    "coollabsio/coolify-examples",
    "coollabsio/coolify.io"
]

from config import CONTRIBUTORS_CHANNEL_ID, CONTRIBUTOR_ROLE_ID

def generate_verification_token():
    """Generate a random verification token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))



class GitHubUsernameVerificationView(View):
    def __init__(self, cog, member, guild):
        super().__init__(timeout=600)  # 10 minutes timeout
        self.cog = cog
        self.member = member
        self.guild = guild
        self.message = None

    @discord.ui.button(label="Enter GitHub Username", style=discord.ButtonStyle.primary)
    async def enter_username(self, interaction: discord.Interaction, button: Button):
        modal = GitHubUsernameVerificationModal(self.cog, self.member, self.guild, interaction.message)
        await interaction.response.send_modal(modal)

class GitHubUsernameVerificationModal(discord.ui.Modal):
    github_username = discord.ui.TextInput(
        label="GitHub Username",
        placeholder="Enter your GitHub username (case-sensitive)",
        required=True,
        max_length=39
    )

    def __init__(self, cog, member, guild, message):
        super().__init__(title="Enter GitHub Username")
        self.cog = cog
        self.member = member
        self.guild = guild
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        github_username = self.github_username.value.strip()

        # Get stored verification token
        stored_token = await self.cog.bot.db.get_verification_token(self.member.id)
        if not stored_token:
            embed = discord.Embed(
                title="❌ Verification Expired",
                description="Your verification token has expired. Please start over.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.message.delete()
            return

        # Verify token in GitHub bio
        verification_result = await self.verify_github_token(github_username, stored_token)

        if not verification_result['success']:
            embed = discord.Embed(
                title="❌ Verification Failed",
                description=verification_result['message'],
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.message.delete()
            return

        # Check if user is a contributor
        is_contributor = await self.cog.bot.db.is_contributor(github_username)

        if is_contributor:
            # Give role
            contributor_role = self.guild.get_role(CONTRIBUTOR_ROLE_ID)
            if contributor_role:
                try:
                    await self.member.add_roles(contributor_role)
                    # Clean up verification token
                    await self.cog.bot.db.remove_verification_token(self.member.id)

                    embed = discord.Embed(
                        title="🎉 Welcome Contributor!",
                        description=f"You have been granted the Contributor role!\n\n"
                                   f"Verified GitHub account: **{github_username}**\n\n"
                                   f"Thank you for your contributions to the project.",
                        color=discord.Color.green()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    await self.message.delete()
                except discord.Forbidden:
                    embed = discord.Embed(
                        title="❌ Permission Error",
                        description="I don't have permission to assign roles. Please contact an admin.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    await self.message.delete()
            else:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Contributor role not found. Please contact an admin.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await self.message.delete()

        else:
            embed = discord.Embed(
                title="❌ Not a Contributor",
                description=f"GitHub account **{github_username}** was verified, but we couldn't find contributions to our repositories.\n\n"
                           "If you've made recent contributions, please wait for the next sync (every 12 hours) "
                           "or ask an admin to sync coolbot's database.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.message.delete()
    async def verify_github_token(self, username: str, expected_token: str) -> dict:
        """Verify that the token appears in the user's GitHub bio"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.github.com/users/{username}") as response:
                    if response.status == 404:
                        return {
                            'success': False,
                            'message': f"GitHub user '{username}' not found. Please check the username and try again."
                        }
                    elif response.status != 200:
                        return {
                            'success': False,
                            'message': f"Failed to fetch GitHub profile for '{username}'. Please try again later."
                        }

                    user_data = await response.json()
                    bio = user_data.get('bio', '') or ''

                    if expected_token in bio:
                        return {
                            'success': True,
                            'message': "GitHub account verified successfully!"
                        }
                    else:
                        return {
                            'success': False,
                            'message': f"Verification token not found in {username}'s GitHub bio. "
                                     f"Please make sure you've added the token exactly as shown and try again."
                        }

        except Exception as e:
            return {
                'success': False,
                'message': f"Error verifying GitHub account: {str(e)}. Please try again later."
            }

class ContributorRoleView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @button(label="Get Contributor Role", style=discord.ButtonStyle.primary, custom_id="get_contributor_role")
    async def get_contributor_role(self, interaction: discord.Interaction, button: Button):
        try:
            if not interaction.guild:
                await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
                return

            member = interaction.user
            if not isinstance(member, discord.Member):
                # Fetch member if it's just a User
                member = interaction.guild.get_member(member.id)
                if not member:
                    await interaction.response.send_message("Could not find your member information.", ephemeral=True)
                    return

            # Check if user already has contributor role
            contributor_role = interaction.guild.get_role(CONTRIBUTOR_ROLE_ID)
            if not contributor_role:
                await interaction.response.send_message("Contributor role not found. Please contact an admin.", ephemeral=True)
                return

            if contributor_role in member.roles:
                await interaction.response.send_message("You already have the contributors role!", ephemeral=True)
                return

            # Start GitHub verification process
            await interaction.response.defer(ephemeral=True)

            # Generate verification token
            token = generate_verification_token()

            # Store token in database
            await self.cog.bot.db.create_verification_token(member.id, token)

            # Show verification instructions
            embed = discord.Embed(
                title="🔐 GitHub Verification Required",
                description="To verify your GitHub account ownership, please follow these steps:\n\n"
                           f"**Step 1: Copy this verification token**\n"
                           f"```\n{token}\n```\n"
                           "**Step 2: Add token to your GitHub profile**\n"
                           "Go to your [GitHub profile](https://github.com/settings/profile) and temporarily add the token above to your bio field.\n\n"
                           "**Step 3: Enter your GitHub username**\n"
                           "Once you've added the token to your bio, click the button below to enter your GitHub username.",
                color=discord.Color.blue()
            )

            embed.set_footer(text="Token expires in 24 hours. You can remove it from your bio after verification.")

            followup_msg = await interaction.followup.send(embed=embed, ephemeral=True, wait=True)
            view = GitHubUsernameVerificationView(self.cog, member, interaction.guild)
            view.message = followup_msg
            await followup_msg.edit(view=view)
            modal = GitHubUsernameVerificationModal(self.cog, member, interaction.guild, followup_msg)
        except Exception as e:
            # Handle case where bot restarted and button is stale
            await interaction.response.send_message(
                "This button is no longer active. Please ping the bot again to get a fresh verification form.",
                ephemeral=True
            )

class ContributorRole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.persistent_view = ContributorRoleView(self)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore our own messages
        if message.author == self.bot.user:
            return

        # Check if message is in contributors channel and mentions the bot
        if message.channel.id == CONTRIBUTORS_CHANNEL_ID and self.bot.user in message.mentions:
            # Send embed with button
            embed = discord.Embed(
                title="Get Contributor Role",
                description="Click the button below to check if you're eligible for the Contributor role based on your GitHub contributions.",
                color=discord.Color.blue()
            )
            view = ContributorRoleView(self)
            await message.channel.send(embed=embed, view=view)
            return

        await self.bot.process_commands(message)

    @app_commands.command(name="contributors-db-sync", description="Force sync contributors from GitHub API (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def contributors_db_sync(self, interaction: discord.Interaction):
        """Force sync contributors from GitHub API"""
        await interaction.response.defer(ephemeral=True)

        try:
            synced_count = await self.sync_contributors_from_github()
            embed = discord.Embed(
                title="Contributors Sync Complete",
                description=f"✅ Successfully synced {synced_count} contributors from GitHub.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="Sync Failed",
                description=f"❌ Error syncing contributors: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def sync_contributors_from_github(self) -> int:
        """Sync contributors from GitHub API for all configured repos"""
        total_contributors = 0

        async with aiohttp.ClientSession() as session:
            for repo in REPOSITORIES:
                if not repo.strip():
                    continue

                contributors = await self.fetch_repo_contributors(session, repo.strip())
                for contributor in contributors:
                    await self.bot.db.add_contributor(contributor['login'], repo)
                    total_contributors += 1

        return total_contributors

    async def fetch_repo_contributors(self, session: aiohttp.ClientSession, repo: str) -> List[dict]:
        """Fetch contributors for a specific repo from GitHub API"""
        url = f"https://api.github.com/repos/{repo}/contributors"
        contributors = []

        page = 1
        while True:
            params = {'page': page, 'per_page': 100}
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    print(f"Error fetching contributors for {repo}: {response.status}")
                    break

                page_contributors = await response.json()
                if not page_contributors:
                    break

                contributors.extend(page_contributors)
                page += 1

                # GitHub API rate limiting
                await asyncio.sleep(0.1)

        return contributors

async def setup(bot: commands.Bot):
    cog = ContributorRole(bot)
    await bot.add_cog(cog)
    bot.add_view(cog.persistent_view)