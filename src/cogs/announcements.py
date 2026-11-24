"""
Cog: Anuncios
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_db, create_announcement, get_announcement, update_announcement, delete_announcement, get_announcements, get_allowed_roles_for_announcements
from src.utils.logger import logger

TYPE_CONFIG = {
    "anuncios": {"channel_key": "ANNOUNCE_CHANNEL_ID", "ping_key": "ANNOUNCE_PING_ROLE_ID", "color": 0x8B00FF, "emoji": "📢"},
    "actualizaciones": {"channel_key": "UPDATE_CHANNEL_ID", "ping_key": "UPDATE_PING_ROLE_ID", "color": 0x00A2FF, "emoji": "🔄"},
    "spoiler": {"channel_key": "SPOILER_CHANNEL_ID", "ping_key": "SPOILER_PING_ROLE_ID", "color": 0x1A1A1A, "emoji": "👀"},
}

def can_use_announcements(member):
    if not member:
        return False
    if member.id == config.OWNER_ID:
        return True
    allowed = get_allowed_roles_for_announcements(member.guild.id)
    return any(r.id in allowed for r in member.roles)

class AnnouncementsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="anuncios", description="Gestiona anuncios, actualizaciones y spoilers")
    @app_commands.describe(
        accion="Acción a realizar",
        tipo="Tipo de anuncio",
        titulo="Título del anuncio",
        descripcion="Descripción del anuncio",
        autor="Autor del anuncio",
        imagen="URL de imagen (opcional)",
        footer="Footer (opcional)",
        tiempo="Tiempo para programar (ej: 30m, 2h, 1d)",
        id="ID del anuncio",
        nuevo_titulo="Nuevo título",
        nueva_descripcion="Nueva descripción",
        nuevo_autor="Nuevo autor",
        nueva_imagen="Nueva imagen",
        nuevo_footer="Nuevo footer"
    )
    @app_commands.choices(accion=[
        app_commands.Choice(name="Crear", value="crear"),
        app_commands.Choice(name="Programar", value="programar"),
        app_commands.Choice(name="Editar", value="editar"),
        app_commands.Choice(name="Borrar", value="borrar"),
        app_commands.Choice(name="Lista", value="lista"),
    ])
    @app_commands.choices(tipo=[
        app_commands.Choice(name="📢 Anuncios", value="anuncios"),
        app_commands.Choice(name="🔄 Actualizaciones", value="actualizaciones"),
        app_commands.Choice(name="👀 Spoiler", value="spoiler"),
    ])
    async def anuncios(self, interaction,
                      accion: str,
                      tipo: str = None,
                      titulo: str = None,
                      descripcion: str = None,
                      autor: str = None,
                      imagen: str = None,
                      footer: str = None,
                      tiempo: str = None,
                      id: int = None,
                      nuevo_titulo: str = None,
                      nueva_descripcion: str = None,
                      nuevo_autor: str = None,
                      nueva_imagen: str = None,
                      nuevo_footer: str = None):
    
        if not can_use_announcements(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        if accion == "crear":
            await self.crear_anuncio(interaction, tipo, titulo, descripcion, autor, imagen, footer)
        elif accion == "programar":
            await self.programar_anuncio(interaction, tipo, tiempo, titulo, descripcion, autor, imagen, footer)
        elif accion == "editar":
            await self.editar_anuncio(interaction, id, nuevo_titulo, nueva_descripcion, nuevo_autor, nueva_imagen, nuevo_footer)
        elif accion == "borrar":
            await self.borrar_anuncio(interaction, id)
        elif accion == "lista":
            await self.lista_anuncios(interaction)
    
    async def crear_anuncio(self, interaction, tipo, titulo, descripcion, autor, imagen, footer):
        if not all([titulo, descripcion, autor]):
            return await interaction.response.send_message("Título, descripción y autor son requeridos.", ephemeral=True)
        
        cfg = TYPE_CONFIG[tipo]
        channel_id = await get_setting(interaction.guild_id, cfg["channel_key"])
        if not channel_id:
            return await interaction.response.send_message(f"Canal para {tipo} no configurado.", ephemeral=True)
        
        ping_role_id = await get_setting(interaction.guild_id, cfg["ping_key"])
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            return await interaction.response.send_message("Canal no encontrado.", ephemeral=True)
        
        if imagen and not imagen.startswith(("http://", "https://")):
            return await interaction.response.send_message("La imagen debe ser una URL válida.", ephemeral=True)
        
        embed = discord.Embed(
            color=cfg["color"],
            title=f"{cfg['emoji']} {titulo}",
            description=descripcion,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=autor)
        if imagen:
            embed.set_image(url=imagen)
        if footer:
            embed.set_footer(text=footer)
        
        content = f"<@&{ping_role_id}>" if ping_role_id else ""
        message = await channel.send(content=content, embed=embed)
        
        from src.database import create_announcement
        await create_announcement(
            interaction.guild_id, tipo, channel_id, str(message.id),
            titulo, descripcion, autor, imagen or None, footer or None,
            ping_role_id or None, "publicado", None, interaction.user.id
        )
        
        await interaction.response.send_message(f"✅ Anuncio de {tipo} publicado.", ephemeral=True)
    
    async def programar_anuncio(self, interaction, tipo, tiempo, titulo, descripcion, autor, imagen, footer):
        if not all([titulo, descripcion, autor, tiempo]):
            return await interaction.response.send_message("Todos los campos son requeridos.", ephemeral=True)
        
        import re
        match = re.match(r"^(\d+)([smhd])$", tiempo.strip(), re.IGNORECASE)
        if not match:
            return await interaction.response.send_message("Formato inválido. Usa: 30s, 10m, 1h, 7d", ephemeral=True)
        
        value = int(match.group(1))
        unit = match.group(2).lower()
        multipliers = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
        duracion_ms = value * multipliers[unit]
        scheduled_at = int(time.time() * 1000) + duracion_ms
        
        cfg = TYPE_CONFIG[tipo]
        channel_id = await get_setting(interaction.guild_id, cfg["channel_key"])
        if not channel_id:
            return await interaction.response.send_message(f"Canal para {tipo} no configurado.", ephemeral=True)
        
        ping_role_id = await get_setting(interaction.guild_id, cfg["ping_key"])
        
        if imagen and not imagen.startswith(("http://", "https://")):
            return await interaction.response.send_message("Imagen inválida.", ephemeral=True)
        
        from src.database import create_announcement
        await create_announcement(
            interaction.guild_id, tipo, channel_id, None,
            titulo, descripcion, autor, imagen or None, footer or None,
            ping_role_id or None, "programado", scheduled_at, interaction.user.id
        )
        
        time_str = f"{value}{unit}"
        await interaction.response.send_message(f"⏰ Anuncio de {tipo} programado para dentro de {time_str}.", ephemeral=True)
    
    async def editar_anuncio(self, interaction, id, nuevo_titulo, nueva_descripcion, nuevo_autor, nueva_imagen, nuevo_footer):
        if not id:
            return await interaction.response.send_message("ID requerido.", ephemeral=True)
        
        from src.database import get_announcement, update_announcement
        ann = await get_announcement(interaction.guild_id, id)
        if not ann:
            return await interaction.response.send_message("Anuncio no encontrado.", ephemeral=True)
        
        if ann["created_by"] != str(interaction.user.id) and interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo el creador o owner pueden editar.", ephemeral=True)
        
        cfg = TYPE_CONFIG[ann["type"]]
        titulo = nuevo_titulo or ann["title"]
        descripcion = nueva_descripcion or ann["description"]
        autor = nuevo_autor or ann["author"]
        imagen = nueva_imagen or ann["image"]
        footer = nuevo_footer or ann["footer"]
        
        if imagen and not imagen.startswith(("http://", "https://")):
            return await interaction.response.send_message("Imagen inválida.", ephemeral=True)
        
        if ann["message_id"]:
            channel = interaction.guild.get_channel(ann["channel_id"])
            if channel:
                try:
                    msg = await channel.fetch_message(int(ann["message_id"]))
                    embed = discord.Embed(
                        color=cfg["color"],
                        title=f"{cfg['emoji']} {titulo}",
                        description=descripcion,
                        timestamp=discord.utils.utcnow()
                    )
                    embed.set_author(name=autor)
                    if imagen:
                        embed.set_image(url=imagen)
                    if footer:
                        embed.set_footer(text=footer)
                    await msg.edit(embed=embed)
                except:
                    pass
        
        await update_announcement(interaction.guild_id, id, {
            "title": titulo, "description": descripcion, "author": autor,
            "image": imagen, "footer": footer
        })
        
        await interaction.response.send_message("✅ Anuncio actualizado.", ephemeral=True)
    
    async def borrar_anuncio(self, interaction, id):
        if not id:
            return await interaction.response.send_message("ID requerido.", ephemeral=True)
        
        from src.database import get_announcement, delete_announcement
        ann = await get_announcement(interaction.guild_id, id)
        if not ann:
            return await interaction.response.send_message("Anuncio no encontrado.", ephemeral=True)
        
        if ann["created_by"] != str(interaction.user.id) and interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo el creador o owner pueden borrar.", ephemeral=True)
        
        if ann["message_id"]:
            channel = interaction.guild.get_channel(ann["channel_id"])
            if channel:
                try:
                    msg = await channel.fetch_message(int(ann["message_id"]))
                    await msg.delete()
                except:
                    pass
        
        await delete_announcement(interaction.guild_id, id)
        await interaction.response.send_message("✅ Anuncio borrado.", ephemeral=True)
    
    async def lista_anuncios(self, interaction):
        from src.database import get_announcements
        announcements = await get_announcements(interaction.guild_id, 20)
        
        if not announcements:
            return await interaction.response.send_message("No hay anuncios.", ephemeral=True)
        
        embed = discord.Embed(title="📋 Lista de Anuncios", color=0x8B00FF)
        for ann in announcements:
            status_emoji = {"publicado": "✅", "programado": "⏰", "borrado": "🗑️"}.get(ann["status"], "❓")
            tipo_emoji = TYPE_CONFIG[ann["type"]]["emoji"]
            embed.add_field(
                name=f"{status_emoji} #{ann['id']} - {tipo_emoji} {ann['type']}",
                value=f"**{ann['title'][:50]}**\nCreado: <t:{ann['created_at']//1000}:R>",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AnnouncementsCog(bot))