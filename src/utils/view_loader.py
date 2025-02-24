import discord
from commands.solved import SolvedButton, NotSolvedButton
from cogs.autoclose import ConfirmCloseView
from commands.devreview import SubmitInfoView

async def load_persistent_views(bot):
    """Load persistent views from database and add them to the bot"""
    if not hasattr(bot, 'db'):
        return
        
    try:
        views = await bot.db.get_all_views()
        loaded_count = 0
        for view_data in views:
            try:
                # Get the channel and thread
                channel = bot.get_channel(view_data['channel_id'])
                thread = bot.get_channel(view_data['thread_id'])
                
                if not channel or not thread:
                    continue

                # Create the appropriate view based on view_type
                view = discord.ui.View(timeout=None)
                if view_data['view_type'] == 'solved':
                    view.add_item(SolvedButton(bot, thread))
                elif view_data['view_type'] == 'not_solved':
                    view.add_item(NotSolvedButton(bot, thread))
                elif view_data['view_type'] == "confirm_close":
                    view = ConfirmCloseView(channel, view_data['post_owner_id'])
                elif view_data['view_type'] == 'submit_info':
                    staff = bot.get_user(view_data['post_owner_id'])
                    view = SubmitInfoView(thread, staff, staff, bot, None)

                # Add the view to the bot with the message_id
                bot.add_view(view, message_id=view_data['message_id'])
                loaded_count += 1
                
            except Exception:
                continue
                
    except Exception:
        raise

async def setup(bot):
    """Setup function for the view_loader extension"""
    await load_persistent_views(bot)
