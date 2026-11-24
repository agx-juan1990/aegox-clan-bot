import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db, get_apply_message_id, set_apply_message_id, get_staff_application_message_id, set_staff_application_message_id
from src.utils.logger import logger

class MemberApplyModal(Modal, title="Postulación a Miembro AEGOX"):
    mc_nick = TextInput(label="Nick de Minecraft", placeholder="Tu nick en Minecraft", max_length=16, min_length=3, required=True)
    edad = TextInput(label="Edad", placeholder="Tu edad (13+)", max_length=3, required=True)
    pais = TextInput(label="País", placeholder="Tu país", max_length=50, required=True)
    tiempo = TextInput(label="Tiempo jugando", placeholder="Ej: 2 años, desde 2020", max_length=100, required=True)
    rol = TextInput(label="Rol (Builder/Farmer/Guerrero)", placeholder="Builder, Farmer o Guerrero", max_length=20, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Validaciones básicas
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
            
            message = await interaction.guild.get_channel(config.channels["member_verify"]).send(embed=embed, view=View())
            await set_application_message_id(app_id, str(message.id))
        
        await interaction.response.send_message("¡Postulación enviada! El staff la revisará pronto.", ephemeral=True)

class MemberRejectModal(Modal, title="Motivo de rechazo"):
    motivo = TextInput(label="Motivo", style=discord.TextStyle.paragraph, max_length=500, required=True)
    
    def __init__(self, app_id: int):
        super().__init__()
        self.app_id = app_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Verificar permisos
        reviewer_role = config.roles["reviewer_member"]
        if not (interaction.user.id == config.OWNER_ID or any(r.id == reviewer_role for r in interaction.user.roles)):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        from src.database import get_db, get_member_application, update_member_application, get_rejection_info, upsert_rejection_info, calculate_next_allowed, log_event
        db = await get_db()
        app = await get_member_application(self.app_id)
        if not app or app["status"] != "pendiente":
            return await interaction.response.send_message("Postulación no encontrada.", ephemeral=True)
        
        # Actualizar rechazo
        rejection = await get_rejection_info(app["user_id"], interaction.guild_id, "miembro")
        new_count = (rejection["count"] if rejection else 0) + 1
        next_allowed = calculate_next_allowed(new_count)
        await upsert_rejection_info(app["user_id"], interaction.guild_id, "miembro", new_count, next_allowed)
        await update_member_application(self.app_id, "rechazado", interaction.user.id, int(__import__('time').time() * 1000), self.motivo.value)
        await log_event(interaction.guild_id, "member_application", f"Rechazado: <@{app['user_id']}> - {self.motivo.value}")
        
        # Notificar
        await interaction.response.send_message("Postulación rechazada.", ephemeral=True)

async def setup(bot):
    pass