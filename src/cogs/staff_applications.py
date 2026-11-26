"""
Cog: Postulaciones de Staff
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db, get_pending_staff_application, create_staff_application, set_staff_application_message_id, is_blacklisted, get_rejection_info
from src.config.ids import CHANNELS, ROLES

class StaffApplyModal(Modal, title="Postulación a Staff AEGOX"):
    nick_golem_discord = TextInput(label="Nick exacto en GolemMC y usuario de Discord", max_length=100, required=True)
    edad_pais_zonahoraria = TextInput(label="Edad, país y zona horaria", max_length=100, required=True)
    tiempo_golem_miembro = TextInput(label="Tiempo en GolemMC y hace cuanto sos miembro activo del clan", max_length=200, required=True)
    otros_clanes = TextInput(label="Estuviste en otros clanes importantes en GolemMC? Por que saliste?", style=discord.TextStyle.paragraph, max_length=500, required=True)
    historial_sanciones = TextInput(label="Historial de sanciones, baneos o mutes. Se sincero.", style=discord.TextStyle.paragraph, max_length=500, required=True)
    por_que_staff = TextInput(label="Por que queres ser staff y que aportarias que no podes hacer como miembro normal?", style=discord.TextStyle.paragraph, max_length=500, required=True)
    horas_disponibilidad = TextInput(label="Cuantas horas al dia y cuantos dias a la semana podes estar conectado vigilando chat y Discord?", max_length=200, required=True)
    microfono_vc = TextInput(label="Tenes microfono y disponibilidad para VC en eventos, guerras o KOTHs?", max_length=200, required=True)
    
    # Preguntas extra para Helper
    guiar_nuevo = TextInput(label="Como recibirias y guiarias a un jugador recien aceptado que no sabe como funciona el clan?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    spam_toxicidad = TextInput(label="Un miembro hace spam o toxicidad. Que sancion aplicas paso a paso?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    pelea_botin = TextInput(label="Dos miembros pelean por reparto de botin o item valioso. Como lo resolves?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    bots_discord = TextInput(label="Sabes manejar bots de Discord, tickets, moderacion, autoroles? Cuales?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    ortografia_paciencia = TextInput(label="Tenes buena ortografia y paciencia para redactar anuncios, reglas o guias?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    
    # Preguntas extra para Mod
    criterios_aceptacion = TextInput(label="Que criterios usarias antes de aceptar a un jugador nuevo para evitar robos o grifeos?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    permisos_base = TextInput(label="Si un miembro nuevo pide permisos en base o cofres principales, como procedes?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    sospecha_filtracion = TextInput(label="Sospechas que un miembro pasa coordenadas o info a clan enemigo. Que haces?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    amigo_roba = TextInput(label="Que harias si descubris que un amigo tuyo roba items o dinero de tesoreria?", style=discord.TextStyle.paragraph, max_length=500, required=False)
    regla_grave_hacks = TextInput(label="Un miembro rompe regla grave cuando no hay lideres conectados. Que haces paso a paso? Y si lo ves usando hacks?", style=discord.TextStyle.paragraph, max_length=500, required=False)

    def __init__(self, puesto: str):
        super().__init__(title=f"Postulación a Staff - {puesto}")
        self.puesto = puesto
        # Ajustar campos según puesto
        if puesto == "Soporte":
            # Solo campos base (ya están definidos)
            pass
        elif puesto == "Helper":
            # Agregar campos extra de Helper
            self.add_item(self.guiar_nuevo)
            self.add_item(self.spam_toxicidad)
            self.add_item(self.pelea_botin)
            self.add_item(self.bots_discord)
            self.add_item(self.ortografia_paciencia)
        elif puesto == "Mod":
            # Agregar campos extra de Helper + Mod
            self.add_item(self.guiar_nuevo)
            self.add_item(self.spam_toxicidad)
            self.add_item(self.pelea_botin)
            self.add_item(self.bots_discord)
            self.add_item(self.ortografia_paciencia)
            self.add_item(self.criterios_aceptacion)
            self.add_item(self.permisos_base)
            self.add_item(self.sospecha_filtracion)
            self.add_item(self.amigo_roba)
            self.add_item(self.regla_grave_hacks)

    async def on_submit(self, interaction):
        # Validaciones
        # ... (validaciones similares a miembro pero más estrictas)
        
        from src.database import get_db, get_pending_staff_application, create_staff_application, set_staff_application_message_id, is_blacklisted, get_rejection_info
        db = await get_db()
        user_id = str(interaction.user.id)
        guild_id = interaction.guild_id
        
        # Verificaciones similares a miembro...
        
        # Crear postulación
        answers = {
            "nick_golem_discord": self.nick_golem_discord.value,
            "edad_pais_zonahoraria": self.edad_pais_zonahoraria.value,
            "tiempo_golem_miembro": self.tiempo_golem_miembro.value,
            "otros_clanes": self.otros_clanes.value,
            "historial_sanciones": self.historial_sanciones.value,
            "por_que_staff": self.por_que_staff.value,
            "horas_disponibilidad": self.horas_disponibilidad.value,
            "microfono_vc": self.microfono_vc.value,
        }
        
        if self.puesto in ["Helper", "Mod"]:
            answers.update({
                "guiar_nuevo": self.guiar_nuevo.value,
                "spam_toxicidad": self.spam_toxicidad.value,
                "pelea_botin": self.pelea_botin.value,
                "bots_discord": self.bots_discord.value,
                "ortografia_paciencia": self.ortografia_paciencia.value,
            })
        
        if self.puesto == "Mod":
            answers.update({
                "criterios_aceptacion": self.criterios_aceptacion.value,
                "permisos_base": self.permisos_base.value,
                "sospecha_filtracion": self.sospecha_filtracion.value,
                "amigo_roba": self.amigo_roba.value,
                "regla_grave_hacks": self.regla_grave_hacks.value,
            })
        
        from src.database import create_staff_application, set_staff_application_message_id
        app_id = await create_staff_application(user_id, guild_id, self.puesto, answers)
        
        # Enviar a canal de verificación
        verify_channel_id = config.channels["staff_verify"]
        channel = interaction.guild.get_channel(config.channels["staff_verify"])
        if channel:
            embed = discord.Embed(
                title=f"Nueva postulación Staff #{app_id}",
                color=0xFFFF00,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Puesto", value=self.puesto, inline=True)
            # ... agregar todos los campos
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"ID: {app_id}")
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="✅ Aprobar", style=discord.ButtonStyle.success, custom_id=f"staff_approve:{app_id}"))
            view.add_item(discord.ui.Button(label="❌ Rechazar", style=discord.ButtonStyle.danger, custom_id=f"staff_reject:{app_id}"))
            
            message = await interaction.guild.get_channel(config.channels["staff_verify"]).send(embed=embed, view=discord.ui.View())
            from src.database import set_staff_application_message_id
            await set_staff_application_message_id(app_id, str(message.id))
        
        await interaction.response.send_message("¡Postulación de staff enviada! El staff la revisará pronto.", ephemeral=True)

class StaffApplicationsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-apply-staff", description="Configura el mensaje de postulaciones de staff (solo owner)")
    async def setup_apply_staff(self, interaction):
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo el owner.", ephemeral=True)
        
        channel = interaction.guild.get_channel(config.channels["staff_apply"])
        if not channel:
            return await interaction.response.send_message("Canal no configurado.", ephemeral=True)
        
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
        ).set_footer(text="AEGOX CLAN")
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Postularse a Staff",
            style=discord.ButtonStyle.primary,
            custom_id="staff_apply_start",
            emoji="⚔️"
        ))
        
        message = await channel.send(embed=embed, view=discord.ui.View())
        from src.database import set_staff_application_message_id
        await set_staff_application_message_id(interaction.guild_id, str(message.id))
        
        await interaction.response.send_message("✅ Mensaje de postulación staff configurado.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StaffApplicationsCog(bot))