"""
Eventos core: on_ready, setup_events
"""
import discord
import time
import asyncio
from src.database import init_db
from src.events.members import on_guild_member_add, on_guild_member_remove
from src.events.interactions import on_interaction
from src.events.invites import on_invite_create, on_invite_delete, on_invite_update
from src.utils.logger import logger
from src.utils.events_auto import AutoEventsSystem
auto_events_system = AutoEventsSystem()
from src.events.verification_webhook import setup_webhooks
from src.commands.verification import ensure_member_apply_message, ensure_staff_apply_message
from src.commands.giveaway_commands import process_expired_giveaways, process_cancelled_giveaways
from src.commands.admin import create_backup_auto
from src.database import get_setting, db
from src.config.ids import CHANNELS, ROLES, GUILDS, VERIFIED_ROLE_ID
from src.utils.logger import logger

async def on_ready(bot):
    """Evento principal de ready"""
    logger.info(f"AEGOX CLAN BOT online - {bot.user} conectado a {len(bot.guilds)} servidor(es).")
    
    # Configurar presencia
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="al mejor clan de golemmc"
        )
    )
    try:
        await bot.user.edit(username="BOT DEL MEJOR CLAN DE GOLEMMC")
    except:
        pass
    
    # Verificar y enviar mensajes de postulación (clan + staff)
    for guild in bot.guilds:
        await ensure_member_apply_message(bot, guild)
        await ensure_staff_apply_message(bot, guild)
    
    # Iniciar loops
    giveaway_task.start(bot)
    trial_task.start()
    announce_task.start()
    backup_task.start()
    top_invites_task.start()
    analytics_flush_task.start()

async def setup_events(bot):
    """Registra todos los event listeners"""
    # Los eventos se registran via decoradores en main.py
    pass

# ============================================================
# LOOPS (TAREAS PROGRAMADAS)
# ============================================================

from discord.ext import tasks

@tasks.loop(seconds=30)
async def giveaway_task(bot):
    """Procesa sorteos expirados y cancelados cada 30s"""
    for guild in bot.guilds:
        try:
            from src.commands.giveaway_commands import process_expired_giveaways, process_cancelled_giveaways
            await process_expired_giveaways(guild)
            await process_cancelled_giveaways(guild)
        except Exception as e:
            logger.error(f"Error en giveaway_task para guild {guild.id}: {e}")

@tasks.loop(hours=24)
async def trial_task():
    """Procesa trials de staff expirados cada 24h"""
    from src.database import db, get_setting, log_to_channel, remove_staff_trial, get_active_staff_trials
    from src.config.ids import GUILDS, ROLES
    from discord import Embed
    
    for guild_id in [1444791873955958878, 1445833036007739576]:
        try:
            expired_trials = await get_active_staff_trials(guild_id)
            for trial in expired_trials:
                try:
                    guild = None  # Se obtiene del bot global
                    # Se procesa en ready via task separada
                except Exception as e:
                    logger.error(f"Error en trial_task para guild {guild_id}: {e}")
        except Exception as e:
            logger.error(f"Error en trial_task: {e}")

@tasks.loop(minutes=1)
async def announce_task():
    """Publica anuncios programados cada minuto"""
    from src.database import db, get_scheduled_announcements, update_announcement
    from src.events.announcements import publish_scheduled_announcement
    
    for guild_id in [1444791873955958878, 1445833036007739576]:
        try:
            scheduled = await get_scheduled_announcements(guild_id)
            for ann in scheduled:
                await publish_scheduled_announcement(guild_id, ann)
        except Exception as e:
            logger.error(f"Error en announce_task para guild {guild_id}: {e}")

@tasks.loop(time=discord.time(hour=3, minute=0))
async def backup_task():
    """Backup diario a las 03:00"""
    try:
        await create_backup_auto()
    except Exception as e:
        logger.error(f"Error en backup automático: {e}")

@tasks.loop(hours=1)
async def top_invites_task():
    """Actualiza top de invites cada hora"""
    from src.database import db
    from src.events.invites import update_top_invites_embed
    
    for guild_id in [1444791873955958878]:
        try:
            await update_top_invites_embed(guild_id)
        except Exception as e:
            logger.error(f"Error actualizando top invites: {e}")

@tasks.loop(seconds=30)
async def analytics_flush_task():
    """Flush periódico de analytics buffer"""
    from src.utils.analytics import analytics_collector
    try:
        await analytics_collector._flush_buffer()
    except Exception as e:
        logger.error(f"Error en analytics flush: {e}")

# Inicialización de tasks
def init_tasks(bot):
    giveaway_task.start(bot)
    trial_task.start()
    announce_task.start()
    backup_task.start()
    top_invites_task.start()
    analytics_flush_task.start()