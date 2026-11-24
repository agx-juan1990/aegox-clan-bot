"""
Cog: Sorteos (Giveaways)
"""
import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from src.config import config
from src.database import get_setting, get_db, create_giveaway, get_giveaway, get_all_entries, update_giveaway, add_giveaway_entry, has_user_entered, get_entry_count, get_allowed_roles_for_giveaways
from src.utils.logger import logger
import re
import time

GIVEAWAY_COLOR = 0x8B00FF

def can_use_giveaways(member):
    if not member:
        return False
    if member.id == config.OWNER_ID:
        return True
    allowed = get_allowed_roles_for_giveaways(member.guild.id)
    return any(r.id in allowed for r in member.roles)

def parse_duration(text: str) -> int:
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

    async def on_submit(self, interaction):
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
        
        ends_at = int(time.time() * 1000) + parse_duration(self.duracion.value)
        
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
        
        message = await channel.send(embed=embed, view=discord.ui.View())
        
        from src.database import create_giveaway
        gw_id = await create_giveaway(
            guild_id, channel_id, str(message.id), self.premio.value, full_desc,
            self.duracion.value, ends_at, int(self.ganadores.value), str(interaction.user.id)
        )
        
        embed.set_footer(text=f"ID: {gw_id}")
        new_view = discord.ui.View()
        new_view.add_item(Button(label="Participar", style=discord.ButtonStyle.primary, custom_id=f"gw_join:{gw_id}", emoji="🎉"))
        await message.edit(embed=embed, view=discord.ui.View())
        
        await db.execute("UPDATE giveaways SET message_id = ? WHERE id = ?", [str(message.id), gw_id])
        await interaction.response.send_message("Sorteo creado.", ephemeral=True)

class GiveawaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="gw-create", description="Crea un sorteo (solo roles permitidos)")
    async def gw_create(self, interaction):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        modal = GiveawayCreateModal()
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="gw-reroll", description="Rerollea ganadores de un sorteo finalizado")
    @app_commands.describe(id="ID del sorteo")
    async def gw_reroll(self, interaction, id: int):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        db = await get_db()
        giveaway = await get_giveaway(guild_id, id)
        if not giveaway:
            return await interaction.response.send_message("Sorteo no encontrado.", ephemeral=True)
        if giveaway["status"] != "finalizado":
            return await interaction.response.send_message("Solo sorteos finalizados.", ephemeral=True)
        
        entries = await get_all_entries(id, guild_id)
        if not entries:
            return await interaction.response.send_message("Sin participantes.", ephemeral=True)
        
        previous = json.loads(giveaway["winners"]) if giveaway["winners"] else []
        available = [e for e in entries if e["user_id"] not in previous]
        if not available:
            return await interaction.response.send_message("Sin participantes nuevos.", ephemeral=True)
        
        import random
        random.shuffle(available)
        new_winners = [e["user_id"] for e in available[:giveaway["winners_count"]]]
        
        await update_giveaway(guild_id, id, { "winners": json.dumps(new_winners) })
        
        embed = discord.Embed(title=f"🎉 Sorteo Rerolleado: {giveaway['premio']}", description=giveaway["descripcion"], color=0x00FF00)
        embed.add_field(name="Nuevos ganadores", value=", ".join(f"<@{w}>" for w in new_winners), inline=False)
        embed.set_footer(text=f"ID: {id} | Rerolleado por {interaction.user}")
        
        try:
            channel = interaction.guild.get_channel(giveaway["channel_id"])
            if channel:
                await channel.send(content=" ".join(f"<@{w}>" for w in new_winners), embed=embed)
        except: pass
        
        for winner_id in new_winners:
            try:
                user = await interaction.client.fetch_user(int(winner_id))
                await user.send(f"¡Ganaste el reroll del sorteo de **{giveaway['premio']}**!")
            except: pass
        
        await interaction.response.send_message("Reroll realizado.", ephemeral=True)
    
    @app_commands.command(name="gw-end", description="Termina un sorteo antes de tiempo")
    @app_commands.describe(id="ID del sorteo")
    async def gw_end(self, interaction, id: int):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        await interaction.response.send_message("Función gw-end - implementar", ephemeral=True)
    
    @app_commands.command(name="gw-cancel", description="Cancela un sorteo")
    @app_commands.describe(id="ID del sorteo")
    async def gw_cancel(self, interaction, id: int):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        await db.execute("UPDATE giveaways SET status = 'cancelado' WHERE id = ?", [id])
        await interaction.response.send_message("Sorteo cancelado.", ephemeral=True)
    
    @app_commands.command(name="gw-list", description="Lista sorteos")
    @app_commands.describe(estado="Filtrar por estado")
    @app_commands.choices(estado=[
        app_commands.Choice(name="Activos", value="activo"),
        app_commands.Choice(name="Finalizados", value="finalizado"),
        app_commands.Choice(name="Cancelados", value="cancelado"),
        app_commands.Choice(name="Todos", value="todos"),
    ])
    async def gw_list(self, interaction, estado: str = "todos"):
        if not can_use_giveaways(interaction.user):
            return await interaction.response.send_message("Sin permisos.", ephemeral=True)
        
        db = await get_db()
        sql = "SELECT * FROM giveaways WHERE guild_id = ?"
        args = [interaction.guild_id]
        if estado != "todos":
            sql += " AND status = ?"
            args.append(estado)
        sql += " ORDER BY created_at DESC LIMIT 20"
        
        giveaways = await db.fetchall(sql, args)
        
        embed = discord.Embed(title="🎉 Lista de Sorteos", color=0x8B00FF)
        for gw in giveaways:
            status_emoji = {"activo": "🟢", "finalizado": "✅", "cancelado": "❌"}.get(gw["status"], "❓")
            embed.add_field(
                name=f"{status_emoji} #{gw['id']} - {gw['premio'][:30]}",
                value=f"Estado: {gw['status']} | Ganadores: {gw['winners_count']} | Termina: <t:{gw['ends_at']//1000}:R>",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiveawaysCog(bot))