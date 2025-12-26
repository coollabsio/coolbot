import discord
from discord.ext import commands
from discord import app_commands
from config import COOLBOT_ADMIN_ROLE_ID
import aiosqlite
from pathlib import Path

class Eval(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="eval", description="Execute SQL command on database (admin only)")
    @app_commands.describe(sql="SQL command to execute")
    async def eval(self, interaction: discord.Interaction, sql: str):
        # Check if user has the coolbot admin role
        if not any(role.id == COOLBOT_ADMIN_ROLE_ID for role in getattr(interaction.user, 'roles', [])):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Access Denied",
                    description="You do not have permission to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        try:
            # Connect to database
            database_dir = Path("database")
            db_path = database_dir / "bot.db"
            
            async with aiosqlite.connect(db_path) as db:
                # Execute the SQL command
                if sql.strip().upper().startswith(('SELECT', 'PRAGMA')):
                    # For queries that return results
                    async with db.execute(sql) as cursor:
                        rows = await cursor.fetchall()
                        column_names = [desc[0] for desc in cursor.description] if cursor.description else []
                        
                        if not rows:
                            result = "No results found."
                        else:
                            # Format results as table
                            result = "```\n"
                            # Header
                            result += " | ".join(column_names) + "\n"
                            result += "-" * (sum(len(col) + 3 for col in column_names) - 1) + "\n"
                            # Rows
                            for row in rows:
                                result += " | ".join(str(cell) for cell in row) + "\n"
                            result += "```"
                else:
                    # For other queries (INSERT, UPDATE, DELETE, etc.)
                    await db.execute(sql)
                    await db.commit()
                    result = "Command executed successfully."
            
            # Send response
            description = f"**Input:** ```sql\n{sql}\n```\n**Output:**\n{result}"
            if len(description) > 4000:  # Embed description limit is 4096, leave some buffer
                description = description[:3997] + "..."
            
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="SQL Evaluation",
                    description=description,
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        
        except Exception as e:
            description = f"**Input:** ```sql\n{sql}\n```\n**Error:** {str(e)}"
            if len(description) > 4000:
                description = description[:3997] + "..."
            
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="SQL Evaluation",
                    description=description,
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Eval(bot))