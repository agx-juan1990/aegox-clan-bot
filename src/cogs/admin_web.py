"""
Cog: Dashboard Web + Analytics
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_db, get_setting
from src.utils.logger import logger
from src.utils.analytics import analytics_collector, metrics_endpoint

@app_commands.command(name="dashboard", description="Dashboard web y analytics")
@app_commands.describe(accion="Acción a realizar")
@app_commands.choices(accion=[
    app_commands.Choice(name="Abrir Dashboard", value="open"),
    app_commands.Choice(name="Stats Prometheus", value="metrics"),
    app_commands.Choice(name="Configurar Web", value="setup"),
])
async def dashboard(interaction, accion: str):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    if accion == "open":
        embed = discord.Embed(
            title="🌐 Dashboard Web AEGOX",
            description=(
                "Accede al dashboard web completo:\n\n"
                "📊 **Analytics**: Usuarios, actividad, retención\n"
                "🛡️ **Anti-Alt**: Detecciones, IPs sospechosas\n"
                "🎫 **Tickets**: Gestión completa\n"
                "📝 **Postulaciones**: Miembro + Staff\n"
                "📊 **Analytics**: Eventos, comandos, actividad\n"
                "⚙️ **Configuración**: Canales, roles, permisos"
            ),
            color=0x8B00FF
        )
        embed.add_field(name="🔗 URL", value="https://dashboard.aegox.clan", inline=False)
        embed.add_field(name="📊 Métricas Prometheus", value="/metrics", inline=True)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="🌐 Abrir Dashboard",
            style=discord.ButtonStyle.link,
            url="https://dashboard.aegox.clan"
        ))
        view.add_item(discord.ui.Button(
            label="📊 Métricas Prometheus",
            style=discord.ButtonStyle.link,
            url="https://dashboard.aegox.clan/metrics"
        ))
        
        await interaction.response.send_message(embed=embed, view=View(), ephemeral=True)
    
    elif accion == "metrics":
        await interaction.response.send_message(
            "📊 Métricas Prometheus: `https://dashboard.aegox.clan/metrics`",
            ephemeral=True
        )
    
    elif accion == "setup":
        modal = DashboardSetupModal()
        await interaction.response.send_modal(modal)

class DashboardSetupModal(Modal, title="Configurar Dashboard Web"):
    jwt_secret = TextInput(label="JWT Secret", placeholder="Secret para JWT tokens", required=True)
    domain = TextInput(label="Dominio", placeholder="dashboard.aegox.clan", required=True)
    port = TextInput(label="Puerto", placeholder="8080", required=True)
    
    async def on_submit(self, interaction):
        from src.database import set_setting
        guild_id = interaction.guild_id
        await set_setting(guild_id, "DASHBOARD_JWT_SECRET", self.jwt_secret.value)
        await set_setting(guild_id, "DASHBOARD_DOMAIN", self.domain.value)
        await set_setting(guild_id, "DASHBOARD_PORT", self.port.value)
        await interaction.response.send_message("✅ Dashboard configurado", ephemeral=True)

@app_commands.command(name="analytics", description="Ver analytics en Discord")
@app_commands.describe(metric="Métrica a ver", period="Período")
@app_commands.choices(metric=[
    app_commands.Choice(name="Usuarios Activos (DAU)", value="dau"),
    app_commands.Choice(name="Comandos Usados", value="commands"),
    app_commands.Choice(name="Postulaciones", value="applications"),
    app_commands.Choice(name="Sorteos", value="giveaways"),
    app_commands.Choice(name="Anti-Alt Detecciones", value="anti_alt"),
])
@app_commands.choices(period=[
    app_commands.Choice(name="Última hora", value="1h"),
    app_commands.Choice(name="Últimas 24h", value="24h"),
    app_commands.Choice(name="Última semana", value="7d"),
    app_commands.Choice(name="Último mes", value="30d"),
])
async def analytics(interaction, metric: str, period: str = "24h"):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    from src.database import db
    guild_id = interaction.guild_id
    period_map = {"1h": 3600000, "24h": 86400000, "7d": 604800000, "30d": 2592000000}
    start_ts = int(time.time() * 1000) - period_map.get(period, 86400000)
    
    if metric == "dau":
        result = await db.fetchone(
            "SELECT COUNT(DISTINCT user_id) as count FROM analytics_events WHERE guild_id = ? AND timestamp >= ?",
            [guild_id, start_ts]
        )
        count = result["count"] if result else 0
        embed = discord.Embed(title="📊 Usuarios Activos (DAU)", color=0x8B00FF)
        embed.add_field(name="Período", value=period, inline=True)
        embed.add_field(name="Usuarios Únicos", value=str(count), inline=True)
    
    elif metric == "commands":
        results = await db.fetchall(
            "SELECT event_data, COUNT(*) as count FROM analytics_events WHERE guild_id = ? AND event_type = 'command_used' AND timestamp >= ? GROUP BY event_data ORDER BY count DESC LIMIT 10",
            [guild_id, start_ts]
        )
        embed = discord.Embed(title="⌨️ Comandos Más Usados", color=0x8B00FF)
        for row in results:
            data = json.loads(row["event_data"])
            cmd = data.get("command", "unknown")
            embed.add_field(name=f"/{cmd}", value=f"{row['count']} usos", inline=True)
    
    elif metric == "anti_alt":
        result = await db.fetchall(
            "SELECT risk_level, COUNT(*) as count FROM alt_detections WHERE guild_id = ? AND created_at >= ? GROUP BY risk_level",
            [guild_id, start_ts]
        )
        embed = discord.Embed(title="🛡️ Detecciones Anti-Alt", color=0xFF6B00)
        for row in result:
            embed.add_field(name=row["risk_level"].capitalize(), value=str(row["count"]), inline=True)
    
    else:
        embed = discord.Embed(title="📊 Analytics", description="Métrica no implementada", color=0x8B00FF)
    
    embed.set_footer(text=f"Período: {period} | AEGOX Analytics")
    await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    pass