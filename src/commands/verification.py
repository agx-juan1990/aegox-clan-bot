"""
Comandos de verificación web + Cloudflare + Auto-asignación de rol
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db
from src.utils.web_verification import web_verification_system
from src.utils.logger import logger
from src.config.ids import CHANNELS, ROLES, VERIFIED_ROLE_ID

@app_commands.command(name="verificacion", description="Sistema de verificación web con Cloudflare")
@app_commands.describe(accion="Acción a realizar")
@app_commands.choices(accion=[
    app_commands.Choice(name="Configurar", value="setup"),
    app_commands.Choice(name="Verificar", value="verify"),
    app_commands.Choice(name="Estado", value="status"),
    app_commands.Choice(name="Test Turnstile", value="test"),
])
async def verificacion(interaction: discord.Interaction, accion: str):
    if interaction.user.id != config.OWNER_ID:
        return await interaction.response.send_message("Solo owner.", ephemeral=True)
    
    if accion == "setup":
        await setup_verification(interaction)
    elif accion == "verify":
        await start_verification(interaction)
    elif accion == "status":
        await verification_status(interaction)
    elif accion == "test":
        await test_turnstile(interaction)

async def setup_verification(interaction):
    """Configura verificación web"""
    modal = VerificationSetupModal()
    await interaction.response.send_modal(modal)

class VerificationSetupModal(Modal, title="Configurar Verificación Web"):
    sitekey = TextInput(label="Turnstile Site Key", placeholder="1x... (sitekey de Cloudflare)", required=True)
    secret = TextInput(label="Turnstile Secret Key", placeholder="0x... (secret de Cloudflare)", required=True)
    verified_role = TextInput(label="Rol Verificado ID", placeholder="1444791874559803498", required=True)
    webhook_url = TextInput(label="Webhook URL (opcional)", placeholder="https://tu-dominio.com/webhook/verify", required=False)
    
    async def on_submit(self, interaction):
        from src.database import db, set_setting
        guild_id = interaction.guild_id
        
        await set_setting(guild_id, "TURNSTILE_SITEKEY", self.sitekey.value)
        await set_setting(guild_id, "TURNSTILE_SECRET", self.secret.value)
        await set_setting(guild_id, "VERIFIED_ROLE_ID", self.verified_role.value)
        if self.webhook_url.value:
            await set_setting(guild_id, "VERIFICATION_WEBHOOK", self.webhook_url.value)
        
        # Configurar verificación
        from src.utils.web_verification import web_verification_system
        await web_verification_system.initialize(interaction.guild_id)
        
        await interaction.response.send_message("✅ Verificación web configurada", ephemeral=True)

async def start_verification(interaction):
    """Inicia proceso de verificación para el usuario"""
    guild_id = interaction.guild_id
    user_id = str(interaction.user.id)
    
    # Verificar si ya está verificado
    verified_role = interaction.guild.get_role(1444791874559803498)
    if verified_role and verified_role in interaction.user.roles:
        return await interaction.response.send_message("✅ Ya estás verificado.", ephemeral=True)
    
    # Verificar configuración
    from src.database import get_setting
    sitekey = await get_setting(interaction.guild_id, "TURNSTILE_SITEKEY")
    if not sitekey:
        return await interaction.response.send_message("❌ Verificación no configurada.", ephemeral=True)
    
    # Crear vista con botón para abrir web
    embed = discord.Embed(
        title="🔐 Verificación Web AEGOX",
        description=(
            "Para acceder al servidor, debes completar la verificación web.\n\n"
            "1. Haz clic en **Verificar Ahora**\n"
            "2. Completa el desafío de Cloudflare\n"
            "3. Recibirás el rol **Verificado** automáticamente\n\n"
            "⚠️ **Antes de verificar:**\n"
            "• No puedes escribir en ningún canal\n"
            "• Solo puedes ver canales\n"
            "• No puedes reaccionar ni usar comandos"
        ),
        color=0x8B00FF
    )
    embed.set_footer(text="AEGOX CLAN • Verificación Segura")
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="🔐 Verificar Ahora",
        style=discord.ButtonStyle.success,
        custom_id="verify_start",
        url=f"https://verificacion.aegox.clan?guild={interaction.guild_id}&user={interaction.user.id}"
    ))
    
    await interaction.response.send_message(embed=embed, view=View(), ephemeral=True)

async def verification_status(interaction):
    """Estado de la verificación"""
    from src.database import get_setting, db
    guild_id = interaction.guild_id
    
    sitekey = await get_setting(guild_id, "TURNSTILE_SITEKEY")
    verified_role = await get_setting(guild_id, "VERIFIED_ROLE_ID")
    
    embed = discord.Embed(title="📊 Estado Verificación", color=0x8B00FF)
    embed.add_field(name="Turnstile Sitekey", value="✅ Configurado" if sitekey else "❌ No configurado", inline=True)
    embed.add_field(name="Rol Verificado", value=f"<@&{verified_role}>" if verified_role else "No configurado", inline=True)
    
    # Stats
    from src.database import db
    stats = await db.fetchone(
        "SELECT COUNT(*) as total, SUM(verified_role_given) as verified FROM web_verifications WHERE guild_id = ?",
        [interaction.guild_id]
    )
    if stats:
        embed.add_field(name="Total Verificaciones", value=str(stats["total"]), inline=True)
        embed.add_field(name="Verificados Exitosos", value=str(stats["verified"]), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def test_turnstile(interaction):
    """Test de configuración Turnstile"""
    await interaction.response.send_message("🔧 Test de Turnstile - Implementar test de conectividad", ephemeral=True)

# ===== HANDLERS DE BOTONES/MODALES =====

async def ensure_member_apply_message(bot, guild):
    """Verifica y envía mensaje de postulación de miembro"""
    try:
        channel_id = await get_setting(guild.id, "MEMBER_APPLY_CHANNEL_ID")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if not channel or not channel.is_text_based():
            return
        
        from src.database import get_apply_message_id, set_apply_message_id
        message_id = await get_apply_message_id(guild.id)
        if message_id:
            try:
                existing = await channel.fetch_message(int(message_id))
                if existing:
                    return
            except:
                pass
        
        embed = discord.Embed(
            title="🟣 Postulación a Miembro AEGOX",
            color=0x8B00FF,
            description=(
                "🟣 ¿Querés ser parte de AEGOX?\n\n"
                "¿Tenés ganas de competir, construir y dominar GolemMC con un clan organizado?\n\n"
                "En AEGOX tenemos roles reales, rangos, ascensos, guerras, KOTHs y eventos todas las semanas.\n\n"
                "📋 REQUISITOS RÁPIDOS\n"
                "• Tener 13+ años\n"
                "• Estar en el Discord de AEGOX\n"
                "• Llevar mínimo 3 días en el Discord\n"
                "• Tener actividad en GolemMC\n"
                "• No estar en blacklist\n\n"
                "🎯 ELEGÍ TU ROL\n"
                "⚔️ Guerrero - PvP, guerras y KOTHs\n"
                "🏗️ Builder - Construcción y bases\n"
                "🌾 Farmer - Granjas y economía\n\n"
                "Apretá el botón de abajo y completá tu postulación por DM. El staff la revisa en 24-48hs.\n\n"
                "AEGOX | GolemMC • FUERZA. HONOR. VICTORIA."
            )
            .set_footer(text="AEGOX CLAN")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse",
            style=discord.ButtonStyle.success,
            custom_id="member_apply_start",
            emoji="📝"
        ))
        
        message = await channel.send(embed=embed, view=discord.ui.View())
        from src.database import set_apply_message_id
        await set_apply_message_id(guild.id, str(message.id))
        logger.info(f"Mensaje de postulación miembro enviado en {channel_id}")
    except Exception as e:
        logger.error(f"Error en ensure_member_apply_message: {e}")

async def ensure_staff_apply_message(bot, guild):
    try:
        channel_id = await get_setting(guild.id, "STAFF_APPLY_CHANNEL_ID")
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if not channel or not channel.is_text_based():
            return
        
        from src.database import get_staff_application_message_id, set_staff_application_message_id
        message_id = await get_staff_application_message_id(guild.id)
        if message_id:
            try:
                existing = await channel.fetch_message(int(message_id))
                if existing:
                    return
            except:
                pass
        
        embed = discord.Embed(
            title="🛡️ Postulación a Staff AEGOX",
            color=0xFF6B00,
            description=(
                "🛡️ ¿Querés ser Staff de AEGOX?\n\n"
                "¿Ya sos parte de AEGOX y querés ayudar a que el clan crezca?\n\n"
                "Ser Staff no es solo tener rango, es ayudar, moderar, revisar postulaciones y representar al clan.\n\n"
                "📋 REQUISITOS RÁPIDOS\n"
                "• Ser miembro de AEGOX hace mínimo 14 días\n"
                "• Tener 15+ años\n"
                "• Llevar mínimo 20 días en el Discord\n"
                "• Tener actividad alta en Discord y GolemMC\n"
                "• No tener sanciones graves\n"
                "• Tener buena comunicación y respeto\n\n"
                "🎯 PUESTOS DE STAFF\n"
                "🛡️ Moderador - Modera chat y ayuda a miembros\n"
                "📋 Reclutador - Revisa postulaciones de miembros\n"
                "🎬 Staff de Eventos - Organiza KOTHs y eventos\n"
                "🎥 Staff Media - Clips, TikToks y publicidad\n\n"
                "Apretá el botón de abajo y completá tu postulación por DM. Solo el staff superior la puede ver.\n\n"
                "AEGOX | GolemMC • Solo para miembros de AEGOX"
            )
            .set_footer(text="AEGOX CLAN")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse a Staff",
            style=discord.ButtonStyle.primary,
            custom_id="staff_apply_start",
            emoji="⚔️"
        ))
        
        message = await channel.send(embed=embed, view=discord.ui.View())
        from src.database import set_staff_application_message_id
        await set_staff_application_message_id(guild.id, str(message.id))
        logger.info(f"Mensaje de postulación staff enviado en {channel_id}")
    except Exception as e:
        logger.error(f"Error en ensure_staff_apply_message: {e}")

def setup(bot):
    pass