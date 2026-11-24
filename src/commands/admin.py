import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_db
from src.utils.logger import logger
import os
import shutil
import psutil
import platform

@app_commands.command(name="stats", description="Estadísticas del bot (solo owner)")
@app_commands.checks.has_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    db = await get_db()
    guild = interaction.guild
    
    member_base_role_id = await get_setting(interaction.guild_id, "MEMBER_BASE_ROLE_ID")
    clan_members = 0
    if member_base_role_id:
        role = interaction.guild.get_role(int(member_base_role_id))
        clan_members = role.member_count if role else 0
    
    staff_roles = [config.roles["staff_base"], config.roles["staff_trial"], 
                   config.roles["staff_soporte"], config.roles["staff_helper"], config.roles["staff_mod"]]
    staff_count = sum(len(interaction.guild.get_role(r).members) for r in staff_roles if interaction.guild.get_role(r))
    
    pending_member = await db.fetchone("SELECT COUNT(*) as c FROM member_applications WHERE guild_id = ? AND status = 'pendiente'", [interaction.guild_id])
    pending_staff = await db.fetchone("SELECT COUNT(*) as c FROM staff_applications WHERE guild_id = ? AND status = 'pendiente'", [interaction.guild_id])
    
    total_valid_invites = await db.fetchone("SELECT SUM(valid) as total FROM invites WHERE guild_id = ?", [interaction.guild_id])
    active_giveaways = await db.fetchone("SELECT COUNT(*) as c FROM giveaways WHERE guild_id = ? AND status = 'activo'", [interaction.guild_id])
    published_announcements = await db.fetchone("SELECT COUNT(*) as c FROM announcements WHERE guild_id = ? AND status = 'publicado'", [interaction.guild_id])
    
    embed = discord.Embed(title="📊 Estadísticas AEGOX", color=0x8B00FF, timestamp=discord.utils.utcnow())
    embed.add_field(name="👥 Miembros totales", value=str(interaction.guild.member_count), inline=True)
    embed.add_field(name="👥 Miembros Clan", value=str(clan_members), inline=True)
    embed.add_field(name="🛡️ Staff", value=str(staff_count), inline=True)
    embed.add_field(name="📝 Postulaciones Miembro", value=str(pending_member["c"] if pending_member else 0), inline=True)
    embed.add_field(name="🛡️ Postulaciones Staff", value=str(pending_staff["c"] if pending_staff else 0), inline=True)
    embed.add_field(name="📊 Invites válidas", value=str(total_valid_invites["total"] if total_valid_invites else 0), inline=True)
    embed.add_field(name="🎉 Sorteos activos", value=str(active_giveaways["c"] if active_giveaways else 0), inline=True)
    embed.add_field(name="📢 Anuncios publicados", value=str(published_announcements["c"] if published_announcements else 0), inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"{__import__('time').time() - bot_start_time:.0f}s", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@app_commands.command(name="consume", description="Consumo de recursos (solo owner)")
@app_commands.checks.has_permissions(administrator=True)
async def consume(interaction: discord.Interaction):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    mem = psutil.Process().memory_info()
    sys_mem = psutil.virtual_memory()
    
    embed = discord.Embed(title="💻 Consumo de Recursos", color=0x8B00FF)
    embed.add_field(name="RAM Bot", value=f"{mem.rss / 1024 / 1024:.1f} MB (RSS) / {mem.vms / 1024 / 1024:.1f} MB (VMS)", inline=False)
    embed.add_field(name="RAM Sistema", value=f"{sys_mem.used / 1024 / 1024:.0f} / {sys_mem.total / 1024 / 1024:.0f} MB ({sys_mem.percent}%)", inline=False)
    embed.add_field(name="CPU", value=f"{psutil.cpu_percent()}%", inline=True)
    embed.add_field(name="Cores", value=str(psutil.cpu_count()), inline=True)
    embed.add_field(name="Plataforma", value=f"{platform.system()} {platform.release()}", inline=True)
    embed.add_field(name="Python", value=sys.version.split()[0], inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@app_commands.command(name="reload", description="Reinicia el bot (solo owner)")
async def reload(interaction: discord.Interaction):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    await interaction.response.send_message("🔄 Reiniciando...", ephemeral=True)
    import sys
    os.execv(sys.executable, [sys.executable] + sys.argv)

@app_commands.command(name="backup", description="Backup manual de la DB (solo owner)")
async def backup(interaction: discord.Interaction):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    try:
        import src.database as db_mod
        backup_path = await db_mod.create_backup_auto()
        await interaction.followup.send(f"✅ Backup creado: {backup_path}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

def setup(bot):
    pass