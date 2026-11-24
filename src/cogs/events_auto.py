"""
Cog: Eventos Automáticos
"""
import discord
from discord import app_commands
from src.config import config
from src.database import get_db, get_setting
from src.utils.events_auto import auto_events_system
from src.utils.logger import logger

class EventsAutoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="evento", description="Gestiona eventos automáticos")
    @app_commands.describe(accion="Acción a realizar")
    @app_commands.choices(accion=[
        app_commands.Choice(name="Crear", value="crear"),
        app_commands.Choice(name="Listar", value="listar"),
        app_commands.Choice(name="Activar/Desactivar", value="toggle"),
        app_commands.Choice(name="Eliminar", value="eliminar"),
    ])
    @app_commands.describe(
        tipo="Tipo de evento",
        nombre="Nombre del evento",
        descripcion="Descripción",
        canal="Canal donde anunciarlo",
        rol="Rol a mencionar",
        schedule="Cron expression (ej: 0 20 * * 0 para domingos 20:00)",
        rewards="Recompensas JSON",
        event_id="ID del evento"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🎁 Drop", value="drop"),
        app_commands.Choice(name="👑 KOTH", value="koth"),
        app_commands.Choice(name="📅 Semanal", value="weekly"),
        app_commands.Choice(name="📅 Mensual", value="monthly"),
        app_commands.Choice(name="🎯 Personalizado", value="custom"),
    ])
    async def evento(self, interaction, accion: str, 
                    tipo: str = None, nombre: str = None, 
                    descripcion: str = None, canal: discord.TextChannel = None,
                    rol: discord.Role = None, schedule: str = None,
                    rewards: str = None, event_id: int = None):
        
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Solo owner.", ephemeral=True)
        
        if accion == "crear":
            if not all([tipo, nombre, canal, schedule]):
                return await interaction.response.send_message("Faltan parámetros requeridos.", ephemeral=True)
            
            from src.database import db
            rewards_json = rewards or "{}"
            
            result = await db.execute(
                """INSERT INTO auto_events (guild_id, name, description, event_type, schedule, channel_id, role_id, rewards, rewards_config, active, next_run, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                [interaction.guild_id, nombre, descripcion or "", tipo, schedule,
                 canal.id, str(rol.id) if rol else None, rewards or "{}", "{}",
                 int(time.time() * 1000), int(time.time() * 1000), str(interaction.user.id)]
            )
            
            event_id = result["last_insert_rowid"]
            
            # Calcular primer next_run
            from src.utils.events_auto import auto_events_system
            next_run = auto_events_system._calculate_next_run(schedule)
            await db.execute("UPDATE auto_events SET next_run = ? WHERE id = ?", [next_run, event_id])
            
            await interaction.response.send_message(f"✅ Evento creado con ID {event_id}", ephemeral=True)
        
        elif accion == "listar":
            from src.database import db
            events = await db.fetchall("SELECT * FROM auto_events WHERE guild_id = ? ORDER BY created_at DESC", [interaction.guild_id])
            
            if not events:
                return await interaction.response.send_message("No hay eventos.", ephemeral=True)
            
            embed = discord.Embed(title="📅 Eventos Automáticos", color=0x8B00FF)
            for ev in events:
                status = "🟢 Activo" if ev["active"] else "🔴 Inactivo"
                next_run = time.strftime("%Y-%m-%d %H:%M", time.localtime(ev["next_run"] / 1000)) if ev["next_run"] else "N/A"
                embed.add_field(
                    name=f"{ev['event_type'].upper()} #{ev['id']} - {ev['name']}",
                    value=f"Estado: {status}\nPróximo: {next_run}\nCanal: <#{ev['channel_id']}>",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif accion == "toggle":
            if not event_id:
                return await interaction.response.send_message("Event ID requerido.", ephemeral=True)
            
            from src.database import db
            event = await db.fetchone("SELECT * FROM auto_events WHERE id = ? AND guild_id = ?", [event_id, interaction.guild_id])
            if not event:
                return await interaction.response.send_message("Evento no encontrado.", ephemeral=True)
            
            new_status = 0 if event["active"] else 1
            await db.execute("UPDATE auto_events SET active = ? WHERE id = ?", [new_status, event_id])
            await interaction.response.send_message(f"Evento {'activado' if new_status else 'desactivado'}.", ephemeral=True)
        
        elif accion == "eliminar":
            if not event_id:
                return await interaction.response.send_message("Event ID requerido.", ephemeral=True)
            
            from src.database import db
            await db.execute("DELETE FROM auto_events WHERE id = ? AND guild_id = ?", [event_id, interaction.guild_id])
            await interaction.response.send_message("Evento eliminado.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EventsAutoCog(bot))