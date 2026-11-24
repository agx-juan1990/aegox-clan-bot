import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_invite_stats, get_db
from src.utils.logger import logger

@app_commands.command(name="invites", description="Consulta las invites de AEGOX")
@app_commands.describe(usuario="Usuario a consultar (opcional, solo owner puede ver de otros)")
async def invites(interaction: discord.Interaction, usuario: discord.User = None):
    target = usuario or interaction.user
    is_owner = interaction.user.id == config.OWNER_ID
    
    if target.id != interaction.user.id and not is_owner:
        return await interaction.response.send_message(
            "No tenés permisos para ver las invites de otro usuario.", ephemeral=True
        )
    
    db = await get_db()
    guild_id = interaction.guild_id
    stats = await get_invite_stats(guild_id, str(target.id))
    
    embed = discord.Embed(
        title=f"📊 Invites de {target.display_name}",
        color=0x8B00FF,
        fields=[
            discord.EmbedField(name="✅ Válidas", value=str(stats.get("valid", 0)), inline=True),
            discord.EmbedField(name="👻 Fakes", value=str(stats.get("fake", 0)), inline=True),
            discord.EmbedField(name="🚪 Se fueron", value=str(stats.get("left", 0)), inline=True),
            discord.EmbedField(name="📊 Total", value=str(stats.get("total", 0)), inline=True),
        ],
        thumbnail=interaction.user.display_avatar.url,
        timestamp=discord.utils.utcnow()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    pass