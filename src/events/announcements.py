"""
Eventos de anuncios: publicación programada
"""
import discord
import time
from src.database import db, get_setting, update_announcement
from src.config.ids import CHANNELS, ROLES, GUILDS
from src.utils.logger import logger

TYPE_CONFIG = {
    "anuncios": { "channel_key": "ANNOUNCE_CHANNEL_ID", "ping_key": "ANNOUNCE_PING_ROLE_ID", "color": 0x8B00FF, "emoji": "📢" },
    "actualizaciones": { "channel_key": "UPDATE_CHANNEL_ID", "ping_key": "UPDATE_PING_ROLE_ID", "color": 0x00A2FF, "emoji": "🔄" },
    "spoiler": { "channel_key": "SPOILER_CHANNEL_ID", "ping_key": "SPOILER_PING_ROLE_ID", "color": 0x1A1A1A, "emoji": "👀" },
}

async def publish_scheduled_announcement(guild_id: int, ann: dict):
    """Publica un anuncio programado"""
    try:
        from src.commands.ping import bot
        guild = bot.get_guild(guild_id) if bot else None
        if not guild:
            return
        
        cfg = TYPE_CONFIG[ann["type"]]
        channel = guild.get_channel(ann["channel_id"])
        if not channel or not channel.is_text_based():
            return
        
        ping_role_id = ann["ping_role_id"]
        content = f"<@&{ping_role_id}>" if ping_role_id else ""
        
        if ann["type"] == "spoiler":
            embed = discord.Embed(
                color=cfg["color"],
                title=f"{cfg['emoji']} {ann['title']}",
                description="Contenido con spoiler. Haz clic en **Ver spoiler** para verlo.",
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=ann["author"])
            if ann["footer"]:
                embed.set_footer(text=ann["footer"])
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="Ver spoiler",
                style=discord.ButtonStyle.primary,
                custom_id=f"spoiler_view:{ann['id']}"
            ))
            
            message = await channel.send(content=content, embed=embed, view=discord.ui.View())
        else:
            embed = discord.Embed(
                color=cfg["color"],
                title=f"{cfg['emoji']} {ann['title']}",
                description=ann["description"],
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=ann["author"])
            if ann["image"]:
                embed.set_image(url=ann["image"])
            if ann["footer"]:
                embed.set_footer(text=ann["footer"])
            
            ping_role_id = ann["ping_role_id"]
            content = f"<@&{ping_role_id}>" if ping_role_id else ""
            message = await channel.send(content=content, embed=embed)
        
        await update_announcement(guild_id, ann["id"], { "status": "publicado", "message_id": str(message.id) })
        logger.info(f"Anuncio programado #{ann['id']} publicado en {guild.name}")
        
    except Exception as e:
        logger.error(f"Error publicando anuncio programado #{ann['id']}: {e}")