import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db, get_allowed_roles_for_giveaways
from src.utils.logger import logger
from src.utils.rate_limiter import rate_limiter

GIVEAWAY_COLOR = 0x8B00FF

def can_use_giveaways(member):
    if not member:
        return False
    if member.id == config.OWNER_ID:
        return True
    allowed = get_allowed_roles_for_giveaways(member.guild.id)
    return any(r.id in allowed for r in member.roles)

def parse_duration(text: str) -> int:
    """Parse duration like 30s, 10m, 1h, 7d to milliseconds"""
    import re
    match = re.match(r"^(\d+)([smhd])$", text.strip(), re.IGNORECASE)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    multipliers = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
    return value * multipliers.get(unit, 0)

class GiveawayCreateModal(Modal, title="Crear Sorteo"):
    premio = TextInput(label="Premio", max_length=200, required=True)
    descripcion = TextInput(label="Descripción", style=discord.TextStyle.paragraph, max_length=1000, required=True)
    duracion = TextInput(label="Duración (ej: 1h, 30m, 7d)", max_length=10, required=True)
    ganadores = TextInput(label="Ganadores (1-10)", max_length=2, required=True)
    requisitos = TextInput(label="Requisitos (opcional)", style=discord.TextStyle.paragraph, max_length=500, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        duracion_ms = parse_duration(self.duracion.value)
        if not duracion_ms:
            return await interaction.response.send_message("Formato inválido. Usa: 30s, 10m, 1h, 7d", ephemeral=True)
        
        try:
            ganadores = int(self.ganadores.value)
            if not 1 <= ganadores <= 10:
                raise ValueError
        except:
            return await interaction.response.send_message("Ganadores: 1-10", ephemeral=True)
        
        db = await get_db()
        guild_id = interaction.guild_id
        channel_id = config.channels["giveaway"]
        channel = interaction.guild.get_channel(config.channels["giveaway"])
        
        if not channel:
            return await interaction.response.send_message("Canal de sorteos no configurado.", ephemeral=True)
        
        full_desc = self.descripcion.value
        if self.requisitos.value:
            full_desc += f"\n\n**Requisitos:** {self.requisitos.value}"
        
        ends_at = int(__import__('time').time() * 1000) + parse_duration(self.duracion.value)
        
        embed = discord.Embed(
            title=f"🎉 Sorteo: {self.premio.value}",
            description=full_desc,
            color=GIVEAWAY_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Ganadores", value=f"{self.ganadores.value}", inline=True)
        embed.add_field(name="Termina", value=f"<t:{ends_at//1000}:R> (<t:{ends_at//1000}:F>)", inline=True)
        embed.add_field(name="Participantes", value="0", inline=True)
        embed.add_field(name="Creador", value=f"<@{interaction.user.id}>", inline=True)
        embed.set_footer(text="ID: 0")
        
        view = discord.ui.View()
        view.add_item(Button(label="Participar", style=discord.ButtonStyle.primary, custom_id="gw_join:0", emoji="🎉"))
        
        message = await channel.send(embed=embed, view=View())
        
        # Crear en DB
        gw_id = await db.execute(
            """INSERT INTO giveaways (guild_id, channel_id, message_id, premio, descripcion, duracion, ends_at, winners_count, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'activo', ?, ?)""",
            [interaction.guild_id, channel_id, str(message.id), self.premio.value, full_desc, 
             self.duracion.value, int(__import__('time').time() * 1000) + parse_duration(self.duracion.value), 
             int(self.ganadores.value), str(interaction.user.id), int(__import__('time').time() * 1000)]
        )
        gw_id = gw_id["last_insert_rowid"]
        
        # Actualizar embed y botón con ID real
        embed.set_footer(text=f"ID: {gw_id}")
        new_view = discord.ui.View()
        new_view.add_item(Button(label="Participar", style=discord.ButtonStyle.primary, custom_id=f"gw_join:{gw_id}", emoji="🎉"))
        await message.edit(embed=embed, view=View())
        
        await db.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", [str(message.id), gw_id])
        await interaction.response.send_message("Sorteo creado.", ephemeral=True)

# Funciones para procesar giveaways (usadas en ready.py)
async def process_expired_giveaways(guild):
    """Procesa sorteos expirados"""
    pass  # Implementado en ready.py

async def process_cancelled_giveaways(guild):
    pass

def setup(bot):
    pass