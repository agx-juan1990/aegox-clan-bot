"""
Cog: Verificación Web + Cloudflare Turnstile
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_setting, get_db
from src.utils.web_verification import web_verification_system
from src.utils.logger import logger
from src.config.ids import TURNSTILE_SITEKEY

class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="verificacion", description="Sistema de verificación web con Cloudflare")
    @app_commands.describe(accion="Acción a realizar")
    @app_commands.choices(accion=[
        app_commands.Choice(name="Configurar", value="setup"),
        app_commands.Choice(name="Verificar", value="verify"),
        app_commands.Choice(name="Estado", value="status"),
        app_commands.Choice(name="Test Turnstile", value="test"),
    ])
    async def verificacion(self, interaction, accion: str):
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo owner.", ephemeral=True)
        
        if accion == "setup":
            await self.setup_verificacion(interaction)
        elif accion == "verify":
            await self.start_verificacion(interaction)
        elif accion == "status":
            await self.verificacion_status(interaction)
        elif accion == "test":
            await self.test_turnstile(interaction)
    
    async def setup_verificacion(self, interaction):
        modal = VerificationSetupModal()
        await interaction.response.send_modal(modal)

class VerificationSetupModal(Modal, title="Configurar Verificación Web"):
    sitekey = TextInput(label="Turnstile Site Key", placeholder="1x... (sitekey de Cloudflare)", required=True)
    secret = TextInput(label="Turnstile Secret Key", placeholder="0x... (secret de Cloudflare)", required=True)
    verified_role = TextInput(label="Rol Verificado ID", placeholder="1444791874559803498", required=True)
    webhook_url = TextInput(label="Webhook URL (opcional)", placeholder="https://tu-dominio.com/webhook/verify", required=False)
    
    async def on_submit(self, interaction):
        from src.database import set_setting
        guild_id = interaction.guild_id
        
        await set_setting(guild_id, "TURNSTILE_SITEKEY", self.sitekey.value)
        await set_setting(guild_id, "TURNSTILE_SECRET", self.secret.value)
        await set_setting(guild_id, "VERIFIED_ROLE_ID", self.verified_role.value)
        if self.webhook_url.value:
            await set_setting(guild_id, "VERIFICATION_WEBHOOK", self.webhook_url.value)
        
        await web_verification_system.initialize(interaction.guild_id)
        
        await interaction.response.send_message("✅ Verificación web configurada", ephemeral=True)

    async def start_verificacion(self, interaction):
        guild_id = interaction.guild_id
        user_id = str(interaction.user.id)
        
        verified_role = interaction.guild.get_role(1444791874559803498)
        if verified_role and verified_role in interaction.user.roles:
            return await interaction.response.send_message("✅ Ya estás verificado.", ephemeral=True)
        
        # Usar el sitekey del config/ids.py (fijo)
        sitekey = TURNSTILE_SITEKEY
        if not sitekey:
            return await interaction.response.send_message("❌ Verificación no configurada (sitekey faltante).", ephemeral=True)
        
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
            url=f"https://dashboard.aegox.clan/verify?guild={interaction.guild_id}&user={interaction.user.id}"
        ))
        
        await interaction.response.send_message(embed=embed, view=View(), ephemeral=True)

    async def verificacion_status(self, interaction):
        from src.database import get_setting, db
        guild_id = interaction.guild_id
        
        sitekey = await get_setting(guild_id, "TURNSTILE_SITEKEY")
        verified_role = await get_setting(guild_id, "VERIFIED_ROLE_ID")
        
        embed = discord.Embed(title="📊 Estado Verificación", color=0x8B00FF)
        embed.add_field(name="Turnstile Sitekey", value="✅ Configurado" if sitekey else "❌ No configurado", inline=True)
        embed.add_field(name="Rol Verificado", value=f"<@&{verified_role}>" if verified_role else "No configurado", inline=True)
        
        stats = await db.fetchone(
            "SELECT COUNT(*) as total, SUM(verified_role_given) as verified FROM web_verifications WHERE guild_id = ?",
            [interaction.guild_id]
        )
        if stats:
            embed.add_field(name="Total Verificaciones", value=str(stats["total"]), inline=True)
            embed.add_field(name="Verificados Exitosos", value=str(stats["verified"]), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def test_turnstile(self, interaction):
        await interaction.response.send_message("🔧 Test de Turnstile - Implementar test de conectividad", ephemeral=True)

async def setup(bot):
    await bot.add_cog(VerificationCog(bot))