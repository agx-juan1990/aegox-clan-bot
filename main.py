#!/usr/bin/env python3
"""
AEGOX CLAN BOT - Python version
Main entry point
"""
import asyncio
import sys
import os

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import discord
from discord.ext import commands
from src.config import config
from src.database import init_db
from src.events.ready import setup_events, on_ready
from src.utils.logger import logger

def main():
    # Validar config
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        sys.exit(1)
    
    # Intents
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True
    intents.invites = True
    
    # Bot
    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
        help_command=None,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="al mejor clan de golemmc"
        ),
        status=discord.Status.dnd
    )
    
    # Guardar referencia global para comandos
    import src.commands.ping as ping_cmd
    ping_cmd.setup(bot)
    
    # Event listeners
    @bot.event
    async def on_ready():
        await on_ready(bot)
    
    @bot.event
    async def on_member_join(member):
        from src.events.ready import on_guild_member_add
        await on_guild_member_add(member)
    
    @bot.event
    async def on_member_remove(member):
        from src.events.ready import on_guild_member_remove
        await on_guild_member_remove(member)
    
    @bot.event
    async def on_interaction(interaction):
        from src.events.ready import on_interaction
        await on_interaction(interaction)
    
    @bot.event
    async def on_invite_create(invite):
        from src.events.ready import on_invite_create
        await on_invite_create(invite)
    
    @bot.event
    async def on_invite_delete(invite):
        from src.events.ready import on_invite_delete
        await on_invite_delete(invite)
    
    @bot.event
    async def on_invite_update(invite):
        from src.events.ready import on_invite_update
        await on_invite_update(invite)
    
    # Cargar comandos slash
    async def load_commands():
        from src.commands import (
            ping, invites, suggestions, applications,
            announcements, giveaways, admin
        )
        
        # Sincronizar comandos
        try:
            # Guild del clan
            clan_guild = discord.Object(id=config.GUILD_ID_CLAN)
            bot.tree.copy_global_to(guild=clan_guild)
            await bot.tree.sync(guild=clan_guild)
            logger.info(f"Comandos sincronizados en Clan ({config.GUILD_ID_CLAN})")
            
            # Guild staff
            staff_guild = discord.Object(id=config.GUILD_ID_STAFF)
            bot.tree.copy_global_to(guild=staff_guild)
            await bot.tree.sync(guild=staff_guild)
            logger.info(f"Comandos sincronizados en Staff ({config.GUILD_ID_STAFF})")
        except Exception as e:
            logger.error(f"Error sincronizando comandos: {e}")
    
    async def startup():
        # Inicializar DB
        await init_db()
        
        # Cargar comandos
        await load_commands()
        
        # Iniciar bot
        await bot.start(config.TOKEN)
    
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        logger.info("Bot detenido por usuario")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()