"""
Eventos de invites: create, delete, update
"""
import discord
import time
from src.database import db, get_setting, log_event, upsert_invite, get_invite_stats
from src.utils.invite_cache import invite_cache, update_invite_cache, delete_invite_cache, fetch_and_cache_guild_invites
from src.utils.logger import logger
from src.config.ids import CHANNELS

async def on_invite_create(invite):
    update_invite_cache(invite.guild.id, invite.code, 
                       str(invite.inviter.id) if invite.inviter else None, invite.uses or 0)

async def on_invite_delete(invite):
    delete_invite_cache(invite.guild.id, invite.code)

async def on_invite_update(invite):
    update_invite_cache(invite.guild.id, invite.code,
                       str(invite.inviter.id) if invite.inviter else None, invite.uses or 0)

# La lógica principal de tracking está en on_guild_member_add (events/members.py)