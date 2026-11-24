"""
Comandos de Tickets
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db
from src.utils.tickets import TicketSystem
from src.utils.logger import logger

ticket_system = TicketSystem()

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
async def ticket(interaction: discord.Interaction, 
                accion: str,
                categoria: str = None,
                asunto: str = None,
                ticket_id: int = None,
                usuario: discord.User = None,
                motivo: str = None):
    
    if accion == "crear":
        await create_ticket(interaction, categoria, asunto)
    elif accion == "cerrar":
        await close_ticket(interaction, ticket_id, motivo)
    elif accion == "reclamar":
        await claim_ticket(interaction, ticket_id)
    elif accion == "transcript":
        await transcript_ticket(interaction, ticket_id)
    elif accion == "add":
        await add_user_ticket(interaction, ticket_id, usuario)
    elif accion == "remove":
        await remove_user_ticket(interaction, ticket_id, usuario)

async def create_ticket(interaction, categoria, asunto):
    if not categoria:
        return await interaction.response.send_message("Categoría requerida.", ephemeral=True)
    if not asunto:
        return await interaction.response.send_message("Asunto requerido.", ephemeral=True)
    
    valid_categories = ["general", "report", "appeal", "purchase", "other"]
    if categoria not in valid_categories:
        return await interaction.response.send_message(f"Categoría inválida. Opciones: {', '.join(valid_categories)}", ephemeral=True)
    
    channel = await ticket_system.create_ticket(interaction.guild, interaction.user, categoria, asunto or "Sin asunto")
    if channel:
        await interaction.response.send_message(f"✅ Ticket creado en {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Límite de tickets abiertos alcanzado (máx 3).", ephemeral=True)

async def close_ticket(interaction, ticket_id, motivo):
    if not ticket_id:
        return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
    if not motivo:
        motivo = "Sin motivo especificado"
    
    success = await ticket_system.close_ticket(interaction.guild, interaction.user, ticket_id, motivo or "Sin motivo")
    if success:
        await interaction.response.send_message("✅ Ticket cerrado.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No se pudo cerrar (sin permisos o ticket no existe).", ephemeral=True)

async def claim_ticket(interaction, ticket_id):
    if not ticket_id:
        return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
    
    success = await ticket_system.claim_ticket(interaction.guild, interaction.user, ticket_id)
    if success:
        await interaction.response.send_message("✅ Ticket reclamado.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No se pudo reclamar.", ephemeral=True)

async def transcript_ticket(interaction, ticket_id):
    if not ticket_id:
        return await interaction.response.send_message("ID de ticket requerido.", ephemeral=True)
    
    transcript = await ticket_system._generate_transcript(ticket_id)
    if transcript:
        # Enviar como archivo
        file = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f"ticket-{ticket_id}-transcript.txt"
        )
        await interaction.response.send_message("📄 Transcript:", file=file, ephemeral=True)
    else:
        await interaction.response.send_message("Ticket no encontrado.", ephemeral=True)

async def add_user_ticket(interaction, ticket_id, usuario):
    if not ticket_id or not usuario:
        return await interaction.response.send_message("Ticket ID y usuario requeridos.", ephemeral=True)
    
    # Verificar permisos
    from src.database import db
    ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ? AND guild_id = ?", [ticket_id, interaction.guild_id])
    if not ticket:
        return await interaction.response.send_message("Ticket no encontrado.", ephemeral=True)
    
    # Verificar permisos (creador, claimer, staff)
    can_manage = (ticket["user_id"] == str(interaction.user.id) or 
                 ticket["claimed_by"] == str(interaction.user.id) or
                 interaction.user.id == config.OWNER_ID or
                 any(r.id in [config.roles["reviewer_member"], config.roles["reviewer_staff"]] for r in interaction.user.roles))
    
    if not can_manage:
        return await interaction.response.send_message("Sin permisos.", ephemeral=True)
    
    # Agregar usuario al canal
    channel = interaction.guild.get_channel(int(ticket["channel_id"]))
    if channel:
        try:
            await channel.set_permissions(usuario, view_channel=True, send_messages=True)
            await interaction.response.send_message(f"✅ {usuario.mention} agregado al ticket.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error agregando usuario.", ephemeral=True)

async def remove_user_ticket(interaction, ticket_id, usuario):
    if not ticket_id or not usuario:
        return await interaction.response.send_message("Ticket ID y usuario requeridos.", ephemeral=True)
    
    channel = interaction.guild.get_channel(int(ticket["channel_id"]))
    if channel:
        try:
            await channel.set_permissions(usuario, overwrite=None)
            await interaction.response.send_message(f"✅ {usuario.mention} removido del ticket.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error removiendo usuario.", ephemeral=True)

def setup(bot):
    pass