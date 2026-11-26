"""
Cog: Postulaciones de Clan
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db, get_pending_application, create_member_application, set_application_message_id, is_blacklisted, get_rejection_info
from src.utils.logger import logger
from src.config.ids import CHANNELS, ROLES

class MemberApplyModal(Modal, title="Postulación a Miembro AEGOX"):
    mc_nick = TextInput(label="Nick de Minecraft", placeholder="Tu nick en Minecraft", max_length=16, min_length=3, required=True)
    edad = TextInput(label="Edad", placeholder="Tu edad (13+)", max_length=3, required=True)
    pais = TextInput(label="País", placeholder="Tu país", max_length=50, required=True)
    tiempo = TextInput(label="Tiempo jugando", placeholder="Ej: 2 años, desde 2020", max_length=100, required=True)
    rol = TextInput(label="Rol (Builder/Farmer/Guerrero)", placeholder="Builder, Farmer o Guerrero", max_length=20, required=True)

    async def on_submit(self, interaction):
        # Validaciones
        try:
            edad_val = int(self.edad.value)
            if edad_val < 13:
                return await interaction.response.send_message("Debes tener 13 años o más.", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("Edad inválida.", ephemeral=True)
        
        rol_val = self.rol.value.lower().strip()
        rol_map = {
            "builder": "Builder", "build": "Builder", "constructor": "Builder", "building": "Builder",
            "farmer": "Farmer", "farm": "Farmer", "agricultor": "Farmer", "granjero": "Farmer", "farming": "Farmer", "cultivos": "Farmer",
            "guerrero": "Guerrero", "warrior": "Guerrero", "pvp": "Guerrero", "fighter": "Guerrero", "luchador": "Guerrero", "combatiente": "Guerrero"
        }
        rol_final = rol_map.get(rol_val)
        if not rol_final:
            return await interaction.response.send_message("Rol inválido. Opciones: Builder, Farmer, Guerrero", ephemeral=True)
        
        # Verificaciones
        from src.database import get_db, get_pending_application, is_blacklisted, get_rejection_info
        db = await get_db()
        user_id = str(interaction.user.id)
        guild_id = interaction.guild_id
        
        # Blacklist
        blacklisted = await is_blacklisted(user_id, guild_id)
        if blacklisted:
            return await interaction.response.send_message(f"Estás en blacklist: {blacklisted['reason']}", ephemeral=True)
        
        # Postulación pendiente
        pending = await get_pending_application(user_id, guild_id)
        if pending:
            return await interaction.response.send_message("Ya tenés una postulación pendiente.", ephemeral=True)
        
        # Cooldown
        from src.database import get_rejection_info
        rejection = await get_rejection_info(user_id, guild_id, "miembro")
        if rejection and rejection["next_allowed_at"] > int(__import__('time').time() * 1000):
            days = (rejection["next_allowed_at"] - int(__import__('time').time() * 1000)) // 86400000 + 1
            return await interaction.response.send_message(f"Cooldown: podés postularte en {days} día(s).", ephemeral=True)
        
        # 3 días en servidor
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.joined_at or (discord.utils.utcnow() - member.joined_at).days < 3:
            return await interaction.response.send_message("Necesitas 3 días en el servidor.", ephemeral=True)
        
        # Crear postulación
        from src.database import create_member_application, set_application_message_id
        app_id = await create_member_application(
            user_id, guild_id, self.mc_nick.value, int(self.edad.value),
            self.pais.value, self.tiempo.value, rol_final
        )
        
        # Enviar a canal de verificación
        verify_channel_id = config.channels["member_verify"]
        channel = interaction.guild.get_channel(config.channels["member_verify"])
        if channel:
            embed = discord.Embed(
                title=f"Nueva postulación Miembro #{app_id}",
                color=0xFFFF00,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Nick MC", value=self.mc_nick.value, inline=True)
            embed.add_field(name="Edad", value=str(self.edad.value), inline=True)
            embed.add_field(name="País", value=self.pais.value, inline=True)
            embed.add_field(name="Tiempo", value=self.tiempo.value, inline=True)
            embed.add_field(name="Rol", value=rol_final, inline=True)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"ID: {app_id}")
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="✅ Aprobar", style=discord.ButtonStyle.success, custom_id=f"member_approve:{app_id}"))
            view.add_item(discord.ui.Button(label="❌ Rechazar", style=discord.ButtonStyle.danger, custom_id=f"member_reject:{app_id}"))
            
            message = await interaction.guild.get_channel(config.channels["member_verify"]).send(embed=embed, view=discord.ui.View())
            await set_application_message_id(app_id, str(message.id))
        
        await interaction.response.send_message("¡Postulación enviada! El staff la revisará pronto.", ephemeral=True)

class ClanApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-apply-member", description="Configura el mensaje de postulaciones de miembro (solo owner)")
    async def setup_apply_member(self, interaction: discord.Interaction):
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo el owner puede usar este comando.", ephemeral=True)
        
        channel_id = config.channels["member_apply"]
        channel = interaction.guild.get_channel(config.channels["member_apply"])
        if not channel or not channel.is_text_based():
            return await interaction.response.send_message("Canal de postulaciones no configurado.", ephemeral=True)
        
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
        ).set_footer(text="AEGOX CLAN")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse",
            style=discord.ButtonStyle.success,
            custom_id="member_apply_start",
            emoji="📝"
        ))
        
        message = await channel.send(embed=embed, view=discord.ui.View())
        from src.database import set_apply_message_id
        await set_apply_message_id(interaction.guild_id, str(message.id))
        
        await interaction.response.send_message("✅ Mensaje de postulación miembro configurado.", ephemeral=True)

    @app_commands.command(name="blacklist-postulacion", description="Gestiona la blacklist de postulaciones")
    @app_commands.describe(accion="Acción", usuario="Usuario", motivo="Motivo")
    @app_commands.choices(accion=[
        app_commands.Choice(name="Agregar", value="add"),
        app_commands.Choice(name="Remover", value="remove"),
        app_commands.Choice(name="Listar", value="list"),
    ])
    async def blacklist_postulacion(self, interaction: discord.Interaction, accion: str, usuario: discord.User = None, motivo: str = None):
        reviewer_role = config.roles["reviewer_member"]
        if not (interaction.user.id == config.OWNER_ID or any(r.id == reviewer_role for r in interaction.user.roles)):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        from src.database import get_db, is_blacklisted, add_to_blacklist, remove_from_blacklist, get_blacklist
        db = await get_db()
        
        if accion == "add":
            if not usuario or not motivo:
                return await interaction.response.send_message("Usuario y motivo requeridos.", ephemeral=True)
            await add_to_blacklist(str(usuario.id), interaction.guild_id, motivo, str(interaction.user.id))
            await interaction.response.send_message(f"✅ {usuario.mention} agregado a blacklist.", ephemeral=True)
        
        elif accion == "remove":
            if not usuario:
                return await interaction.response.send_message("Usuario requerido.", ephemeral=True)
            await remove_from_blacklist(str(usuario.id), interaction.guild_id)
            await interaction.response.send_message(f"✅ {usuario.mention} removido de blacklist.", ephemeral=True)
        
        elif accion == "list":
            blacklist = await get_blacklist(interaction.guild_id)
            if not blacklist:
                return await interaction.response.send_message("Blacklist vacía.", ephemeral=True)
            
            embed = discord.Embed(title="🚫 Blacklist de Postulaciones", color=0xFF0000)
            for entry in blacklist:
                embed.add_field(name=f"<@{entry['user_id']}>", value=f"Motivo: {entry['reason']}\nPor: <@{entry['by_user']}>", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ClanApplicationsCog(bot))