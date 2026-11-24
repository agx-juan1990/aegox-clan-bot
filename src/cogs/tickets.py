"""
Cog: Tickets
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db
from src.utils.tickets import TicketSystem
from src.utils.logger import logger

ticket_system = TicketSystem()

class TicketCreateModal(Modal, title="Crear Ticket"):
    categoria = TextInput(label="Categoría", placeholder="general, report, appeal, purchase, other", max_length=20, required=True)
    asunto = TextInput(label="Asunto", max_length=100, required=True)

    async def on_submit(self, interaction):
        valid_categories = ["general", "report", "appeal", "purchase", "other"]
        if self.categoria.value not in valid_categories:
            return await interaction.response.send_message(f"Categoría inválida. Opciones: {', '.join(valid_categories)}", ephemeral=True)
        
        channel = await ticket_system.create_ticket(interaction.guild, interaction.user, self.categoria.value, self.asunto.value or "Sin asunto")
        if channel:
            await interaction.response.send_message(f"✅ Ticket creado en {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Límite de tickets abiertos alcanzado (máx 3).", ephemeral=True)

class TicketCloseModal(Modal, title="Cerrar Ticket"):
    motivo = TextInput(label="Motivo del cierre", style=discord.TextStyle.paragraph, max_length=500, required=True)

    def __init__(self, ticket_id: int):
        super().__init__()
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction):
        success = await ticket_system.close_ticket(interaction.guild, interaction.user, self.ticket_id, self.motivo.value)
        if success:
            await interaction.response.send_message("✅ Ticket cerrado.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No se pudo cerrar (sin permisos o ticket no existe).", ephemeral=True)

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ticket", description="Sistema de tickets")
    @app_commands.describe(accion="Acción a realizar")
    @app_commands.choices(accion=[
        app_commands.Choice(name="Crear", value="crear"),
        app_commands.Choice(name="Cerrar", value="cerrar"),
        app_commands.Choice(name="Reclamar", value="reclamar"),
        app_commands.Choice(name="Transcript", value="transcript"),
        app_commands.Choice(name="Agregar Usuario", value="add"),
        app_commands.Choice(name="Remover Usuario", value="remove"),
    ])
    @app_commands.describe(
        categoria="Categoría del ticket",
        asunto="Asunto del ticket",
        ticket_id="ID del ticket",
        usuario="Usuario a agregar/remover",
        motivo="Motivo del cierre"
    )
    async def ticket(self, interaction, 
                    accion: str,
                    categoria: str = None,
                    asunto: str = None,
                    ticket_id: int = None,
                    usuario: discord.User = None,
                    motivo: str = None):
        
        if accion == "crear":
            if not categoria or not asunto:
                return await interaction.response.send_message("Categoría y asunto requeridos.", ephemeral=True)
            channel = await ticket_system.create_ticket(interaction.guild, interaction.user, categoria, asunto)
            if channel:
                await interaction.response.send_message(f"✅ Ticket creado en {channel.mention}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Límite de tickets abiertos alcanzado (máx 3).", ephemeral=True)
        
        elif accion == "cerrar":
            if not ticket_id:
                return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
            modal = TicketCloseModal(ticket_id)
            await interaction.response.send_modal(modal)
        
        elif accion == "reclamar":
            if not ticket_id:
                return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
            success = await ticket_system.claim_ticket(interaction.guild, interaction.user, ticket_id)
            await interaction.response.send_message("✅ Ticket reclamado." if success else "❌ No se pudo reclamar.", ephemeral=True)
        
        elif accion == "transcript":
            if not ticket_id:
                return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
            transcript = await ticket_system._generate_transcript(ticket_id)
            if transcript:
                file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"ticket-{ticket_id}-transcript.txt"
                )
                await interaction.response.send_message("📄 Transcript:", file=file, ephemeral=True)
            else:
                await interaction.response.send_message("Ticket no encontrado.", ephemeral=True)
        
        elif accion == "add":
            if not ticket_id or not usuario:
                return await interaction.response.send_message("Ticket ID y usuario requeridos.", ephemeral=True)
            
            from src.database import db
            ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ? AND guild_id = ?", [ticket_id, interaction.guild_id])
            if not ticket:
                return await interaction.response.send_message("Ticket no encontrado.", ephemeral=True)
            
            # Verificar permisos
            can_manage = (ticket["user_id"] == str(interaction.user.id) or 
                         ticket["claimed_by"] == str(interaction.user.id) or
                         interaction.user.id == config.OWNER_ID or
                         any(r.id in [config.roles["reviewer_member"], config.roles["reviewer_staff"]] for r in interaction.user.roles))
            
            if not can_manage:
                return await interaction.response.send_message("Sin permisos.", ephemeral=True)
            
            channel = interaction.guild.get_channel(int(ticket["channel_id"]))
            if channel:
                try:
                    await channel.set_permissions(usuario, view_channel=True, send_messages=True)
                    await interaction.response.send_message(f"✅ {usuario.mention} agregado al ticket.", ephemeral=True)
                except:
                    await interaction.response.send_message("❌ Error agregando usuario.", ephemeral=True)
        
        elif accion == "remove":
            if not ticket_id or not usuario:
                return await interaction.response.send_message("Ticket ID y usuario requeridos.", ephemeral=True)
            
            channel = interaction.guild.get_channel(int(ticket["channel_id"]))
            if channel:
                try:
                    await channel.set_permissions(usuario, overwrite=None)
                    await interaction.response.send_message(f"✅ {usuario.mention} removido del ticket.", ephemeral=True)
                except:
                    await interaction.response.send_message("❌ Error removiendo usuario.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))