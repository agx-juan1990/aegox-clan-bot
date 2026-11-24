import discord
from discord import app_commands
from src.config import config
from src.database import get_setting
from src.utils.logger import logger

@app_commands.command(name="ping", description="Responde con la latencia, uptime y estadísticas del bot.")
async def ping(interaction: discord.Interaction):
    sent = await interaction.response.send_message("Calculando...", ephemeral=True)
    latency = (discord.utils.utcnow() - interaction.created_at).total_seconds() * 1000
    api_latency = round(bot.latency * 1000)
    uptime = format_uptime(__import__('time').time() - bot_start_time)
    
    guild = interaction.guild
    member_count = guild.member_count if guild else 0
    clan_member_count = 0
    if guild:
        member_base_role_id = await get_setting(guild.id, "MEMBER_BASE_ROLE_ID")
        if member_base_role_id:
            role = guild.get_role(int(member_base_role_id))
            clan_member_count = role.member_count if role else 0
    
    embed = discord.Embed(
        title="🏓 Pong!",
        color=0x8B00FF,
        fields=[
            discord.EmbedField(name="Latencia Bot", value=f"{latency:.0f}ms", inline=True),
            discord.EmbedField(name="Latencia API", value=f"{api_latency}ms", inline=True),
            discord.EmbedField(name="Uptime", value=uptime, inline=True),
            discord.EmbedField(name="Usuarios en DC", value=str(member_count), inline=True),
            discord.EmbedField(name="Miembros Clan", value=str(clan_member_count), inline=True),
        ],
        timestamp=discord.utils.utcnow()
    )
    await interaction.edit_original_response(content=None, embed=embed)

def format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

# Variables globales que se setean desde main
bot = None
bot_start_time = 0

def setup(bot_instance):
    global bot, bot_start_time
    bot = bot_instance
    bot_start_time = __import__('time').time()