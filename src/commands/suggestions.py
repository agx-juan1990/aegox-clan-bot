import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_db
from src.utils.logger import logger
from src.utils.rate_limiter import rate_limiter, SUGGESTION_APPLICATION_COOLDOWN

@app_commands.command(name="sugerencia", description="Envía una sugerencia al staff del clan")
@app_commands.describe(texto="Escribe tu sugerencia (máx 1000 caracteres)")
@app_commands.checks.cooldown(1, 30, key=lambda i: (i.guild_id, i.user.id))
async def sugerencia(interaction: discord.Interaction, texto: str):
    # Rate limit adicional
    allowed, remaining = rate_limiter.check_cooldown(
        str(interaction.user.id), "sugerencia", SUGGESTION_APPLICATION_COOLDOWN
    )
    if not allowed:
        return await interaction.response.send_message(
            f"Esperá {remaining}s antes de enviar otra sugerencia.", ephemeral=True
        )
    
    # Verificar canal correcto
    create_channel_id = config.channels["suggest_create"]
    if interaction.channel_id != create_channel_id:
        return await interaction.response.send_message(
            f"Solo se puede usar /sugerencia en el canal de sugerencias (<#{create_channel_id}>).",
            ephemeral=True
        )
    
    # Crear sugerencia
    db = await get_db()
    result = await db.execute(
        """INSERT INTO suggestions (guild_id, user_id, text, message_id, channel_id, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pendiente', ?)""",
        [interaction.guild_id, str(interaction.user.id), texto, "", create_channel_id, 
         int(__import__('time').time() * 1000)]
    )
    suggestion_id = result["last_insert_rowid"]
    
    # Embed en canal de lista
    list_channel_id = config.channels["suggest_list"]
    list_channel = interaction.guild.get_channel(config.channels["suggest_list"])
    if list_channel:
        embed = discord.Embed(
            title=f"Nueva sugerencia #{suggestion_id}",
            description=texto,
            color=0xFFFF00,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Estado", value="⏳ Pendiente", inline=True)
        embed.add_field(name="Votos", value="👍 0 | 👎 0", inline=True)
        embed.set_footer(text=f"ID: #{suggestion_id}")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="👍 A favor", style=discord.ButtonStyle.success, custom_id=f"sugvote:up:{suggestion_id}"))
        view.add_item(discord.ui.Button(label="👎 En contra", style=discord.ButtonStyle.danger, custom_id=f"sugvote:down:{suggestion_id}"))
        view.add_item(discord.ui.Button(label="✅ Aprobar", style=discord.ButtonStyle.primary, custom_id=f"sugdec:aprobar:{suggestion_id}"))
        view.add_item(discord.ui.Button(label="❌ Rechazar", style=discord.ButtonStyle.danger, custom_id=f"sugdec:rechazar:{suggestion_id}"))
        
        message = await interaction.guild.get_channel(config.channels["suggest_list"]).send(embed=embed, view=discord.ui.View())
        await __import__('src.database').database.db.execute(
            "UPDATE suggestions SET message_id = ? WHERE id = ?",
            [str(message.id), suggestion_id]
        )
    
    await interaction.response.send_message("Tu sugerencia fue publicada.", ephemeral=True)

async def setup(bot):
    pass