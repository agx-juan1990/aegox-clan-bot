"""
Cog core: eventos base del bot
"""
import discord
from discord.ext import commands
from src.events.core import on_ready, setup_events
from src.events.members import on_guild_member_add, on_guild_member_remove
from src.events.interactions import on_interaction
from src.events.invites import on_invite_create, on_invite_delete, on_invite_update
from src.events.webhooks import setup_webhooks
from src.utils.logger import logger

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        from src.events.core import on_ready
        await on_ready(self.bot)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        from src.events.members import on_guild_member_add
        await on_guild_member_add(member)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        from src.events.members import on_guild_member_remove
        await on_guild_member_remove(member)
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        from src.events.interactions import on_interaction
        await on_interaction(interaction)
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        from src.events.invites import on_invite_create
        await on_invite_create(invite)
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        from src.events.invites import on_invite_delete
        await on_invite_delete(invite)
    
    @commands.Cog.listener()
    async def on_invite_update(self, invite):
        from src.events.invites import on_invite_update
        await on_invite_update(invite)

async def setup(bot):
    await bot.add_cog(CoreCog(bot))