"""
Cog: Anti-Alt commands
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_db
from src.utils.anti_alt import anti_alt_detector
from src.utils.logger import logger

class AntiAltCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="anti-alt", description="Sistema Anti-Alt")
    @app_commands.describe(accion="Acción a realizar")
    @app_commands.choices(accion=[
        app_commands.Choice(name="Analizar Usuario", value="analyze"),
        app_commands.Choice(name="Ver Detecciones", value="detections"),
        app_commands.Choice(name="Configurar", value="config"),
        app_commands.Choice(name="Marcar Falso Positivo", value="false_positive"),
    ])
    @app_commands.describe(usuario="Usuario a analizar", detection_id="ID de la detección")
    async def anti_alt(self, interaction, accion: str, usuario: discord.User = None, detection_id: int = None):
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo owner.", ephemeral=True)
        
        if accion == "analyze":
            if not usuario:
                return await interaction.response.send_message("Usuario requerido.", ephemeral=True)
            
            await interaction.response.defer(ephemeral=True)
            
            # Obtener IP/HWID del usuario (en producción vendría de la verificación web)
            result = await anti_alt_detector.analyze_user(
                interaction.guild_id, str(usuario.id)
            )
            
            embed = discord.Embed(
                title=f"🛡️ Análisis Anti-Alt: {usuario.display_name}",
                color=0xFF6B00 if result["risk_score"] > 0.4 else 0x8B00FF
            )
            embed.add_field(name="Risk Score", value=f"{result['risk_score']:.0%}", inline=True)
            embed.add_field(name="Risk Level", value=result["risk_level"].capitalize(), inline=True)
            embed.add_field(name="Acción", value=result["action"], inline=True)
            
            if result["detections"]:
                det_text = "\n".join([f"• {d['type']}: {d['confidence']:.0%}" for d in result["detections"]])
                embed.add_field(name="Detecciones", value=det_text, inline=False)
            
            if result["matched_users"]:
                matched = ", ".join(f"<@{u}>" for u in result["matched_users"][:5])
                embed.add_field(name="Usuarios Relacionados", value=matched, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif accion == "detections":
            from src.database import db
            detections = await db.fetchall(
                "SELECT * FROM alt_detections WHERE guild_id = ? ORDER BY created_at DESC LIMIT 20",
                [interaction.guild_id]
            )
            
            if not detections:
                return await interaction.response.send_message("No hay detecciones.", ephemeral=True)
            
            embed = discord.Embed(title="🛡️ Últimas Detecciones Anti-Alt", color=0xFF6B00)
            for det in detections:
                risk_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(det["risk_level"], "⚪")
                embed.add_field(
                    name=f"{risk_emoji} #{det['id']} - <@{det['user_id']}>",
                    value=f"Score: {det['confidence']:.0%} | Tipo: {det['detection_type']} | Estado: {det['status']}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif accion == "false_positive":
            if not detection_id:
                return await interaction.response.send_message("Detection ID requerido.", ephemeral=True)
            
            from src.database import db
            await db.execute(
                "UPDATE alt_detections SET status = 'false_positive', reviewed_by = ?, reviewed_at = ? WHERE id = ?",
                [str(interaction.user.id), int(time.time() * 1000), detection_id]
            )
            await interaction.response.send_message("✅ Marcado como falso positivo.", ephemeral=True)
        
        elif accion == "config":
            # Configuración de thresholds
            await interaction.response.send_message("⚙️ Configuración anti-alt - Implementar panel de config", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AntiAltCog(bot))