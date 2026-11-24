"""
Sistema de Tickets completo
"""
import discord
import time
from typing import Optional, List, Dict
from src.database import db, get_setting, log_event, log_to_channel
from src.config.ids import CHANNELS, ROLES, GUILDS
from src.utils.logger import logger

class TicketSystem:
    def __init__(self):
        self.category_map = {
            "general": "📋 General",
            "report": "🚨 Reporte",
            "appeal": "⚖️ Apelación",
            "purchase": "💰 Compra",
            "other": "📦 Otro"
        }
    
    async def create_ticket(self, guild: discord.Guild, user: discord.User, 
                           category: str, subject: str) -> Optional[discord.TextChannel]:
        """Crea un nuevo ticket"""
        # Verificar límite de tickets abiertos
        open_tickets = await self._get_user_open_tickets(guild.id, user.id)
        if len(open_tickets) >= 3:
            return None
        
        # Crear canal
        category_name = self.category_map.get(category, "📋 General")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.get_member(int(user.id)): discord.PermissionOverwrite(
                view_channel=True, send_messages=True, attach_files=True, embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True, manage_channels=True
            )
        }
        
        # Agregar permisos para staff
        reviewer_role_id = ROLES.get("reviewer_member")
        reviewer_role = guild.get_role(reviewer_role_id) if reviewer_role_id else None
        if reviewer_role:
            overwrites[reviewer_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )
        
        staff_reviewer_id = ROLES.get("reviewer_staff")
        staff_reviewer = guild.get_role(ROLES.get("reviewer_staff"))
        if staff_reviewer:
            overwrites[staff_reviewer] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True
            )
        
        # Crear canal
        channel_name = f"ticket-{user.name}-{int(time.time())}"
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Ticket de {user.name} ({user.id}) - {category}"
        )
        
        # Guardar en DB
        from src.database import db
        ticket_id = await db.execute(
            """INSERT INTO tickets (guild_id, channel_id, user_id, category, status, subject, created_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?)""",
            [guild.id, str(channel.id), str(user.id), category, subject, int(time.time() * 1000)]
        )
        
        # Embed inicial
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} - {self.category_map.get(category, category)}",
            color=0x8B00FF,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Usuario", value=f"<@{user.id}>", inline=True)
        embed.add_field(name="📂 Categoría", value=category_name, inline=True)
        embed.add_field(name="📋 Asunto", value=subject, inline=False)
        embed.set_footer(text=f"Ticket ID: {ticket_id} | Usuario: {user.id}")
        
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="🔒 Cerrar", style=discord.ButtonStyle.danger, custom_id=f"ticket_close:{ticket_id}"))
        view.add_item(discord.ui.Button(label="📝 Reclamar", style=discord.ButtonStyle.primary, custom_id=f"ticket_claim:{ticket_id}"))
        view.add_item(discord.ui.Button(label="📄 Transcript", style=discord.ButtonStyle.secondary, custom_id=f"ticket_transcript:{ticket_id}"))
        
        embed.set_author(name=f"Ticket de {user.display_name}", icon_url=user.display_avatar.url)
        
        channel = guild.get_channel(channel_id)
        if channel:
            msg = await channel.send(embed=embed, view=discord.ui.View())
            # Agregar botones persistentes
            await channel.send(view=TicketView(ticket_id))
        
        return channel
    
    async def claim_ticket(self, guild, user, ticket_id: int) -> bool:
        from src.database import db
        ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ? AND guild_id = ?", [ticket_id, guild_id])
        if not ticket or ticket["status"] != "open":
            return False
        
        await db.execute(
            "UPDATE tickets SET status = 'claimed', claimed_by = ?, claimed_at = ? WHERE id = ?",
            [str(user.id), int(time.time() * 1000), ticket_id]
        )
        
        channel = guild.get_channel(int(ticket["channel_id"]))
        if channel:
            await channel.send(f"🎫 Ticket reclamado por {user.mention}")
        
        return True
    
    async def close_ticket(self, guild, user, ticket_id: int, reason: str = "Sin motivo") -> bool:
        from src.database import db
        ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ? AND guild_id = ?", [ticket_id, guild.id])
        if not ticket:
            return False
        
        # Verificar permisos
        can_close = (ticket["user_id"] == str(user.id) or 
                    user.id == config.OWNER_ID or
                    any(r.id in [config.roles["reviewer_member"], ROLES["reviewer_staff"]] for r in user.roles))
        
        if not can_close:
            return False
        
        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ?, close_reason = ? WHERE id = ?",
            [int(time.time() * 1000), str(user.id), reason, ticket_id]
        )
        
        # Generar transcript
        transcript = await self._generate_transcript(ticket_id)
        await db.execute("UPDATE tickets SET transcript_url = ? WHERE id = ?", [transcript, ticket_id])
        
        # Notificar
        channel = guild.get_channel(int(ticket["channel_id"]))
        if channel:
            embed = discord.Embed(
                title="🔒 Ticket Cerrado",
                description=f"Cerrado por {user.mention}\nMotivo: {reason}",
                color=0xFF0000,
                timestamp=discord.utils.utcnow()
            )
            await channel.send(embed=embed)
            await channel.edit(archived=True, locked=True)
        
        return True
    
    async def add_message(self, ticket_id: int, user_id: str, content: str, attachments: list = None):
        from src.database import db
        await db.execute(
            """INSERT INTO ticket_messages (ticket_id, user_id, content, attachments, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            [ticket_id, user_id, content, json.dumps(attachments or []), int(time.time() * 1000)]
        )
    
    async def _get_user_open_tickets(self, guild_id: int, user_id: str) -> List[dict]:
        from src.database import db
        return await db.fetchall(
            "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND status IN ('open', 'claimed')",
            [guild_id, user_id]
        )
    
    async def _generate_transcript(self, ticket_id: int) -> str:
        from src.database import db
        messages = await db.fetchall(
            """SELECT tm.*, u.username FROM ticket_messages tm
               LEFT JOIN users u ON tm.user_id = u.user_id
               WHERE tm.ticket_id = ? ORDER BY tm.created_at""",
            [ticket_id]
        )
        
        ticket = await db.fetchone("SELECT * FROM tickets WHERE id = ?", [ticket_id])
        if not ticket:
            return ""
        
        lines = [f"Ticket #{ticket_id} - {ticket['subject']}", "=" * 50]
        for msg in messages:
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg["created_at"] / 1000))
            user = msg.get("username", msg["user_id"])
            attachments = f" [Adjuntos: {msg['attachments']}]" if msg.get("attachments") else ""
            lines.append(f"[{ts}] {user}: {msg['content']}{attachments}")
        
        content = "\n".join(lines)
        
        # Subir a pastebin o guardar como archivo
        # Por ahora retornamos el contenido
        return content[:1900]  # Límite Discord

def setup(bot):
    pass