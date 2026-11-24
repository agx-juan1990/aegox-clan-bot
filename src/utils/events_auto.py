"""
Sistema de Eventos Automáticos
Eventos semanales, drops, KOTHs, leaderboards
"""
import discord
import time
import random
from typing import Dict, List, Optional
from src.database import db, get_setting, log_event
from src.config.ids import CHANNELS, ROLES, GUILDS
from src.utils.logger import logger

class AutoEventsSystem:
    def __init__(self):
        self.running_events = {}
    
    async def process_scheduled_events(self, bot):
        """Procesa eventos programados"""
        for guild_id in [GUILDS["clan"], GUILDS["staff"]]:
            try:
                events = await db.fetchall(
                    "SELECT * FROM auto_events WHERE guild_id = ? AND active = 1 AND next_run <= ?",
                    [guild_id, int(time.time() * 1000)]
                )
                
                for event in events:
                    await self._execute_event(bot, event)
                    
                    # Calcular próxima ejecución
                    next_run = self._calculate_next_run(event["schedule"])
                    await db.execute(
                        "UPDATE auto_events SET last_run = ?, next_run = ? WHERE id = ?",
                        [int(time.time() * 1000), next_run, event["id"]]
                    )
            except Exception as e:
                logger.error(f"Error procesando eventos para guild {guild_id}: {e}")
    
    async def _execute_event(self, bot, event):
        guild = bot.get_guild(event["guild_id"])
        if not guild:
            return
        
        channel = guild.get_channel(event["channel_id"])
        if not channel:
            return
        
        try:
            if event["event_type"] == "drop":
                await self._execute_drop_event(guild, channel, event)
            elif event["event_type"] == "koth":
                await self._execute_koth_event(guild, channel, event)
            elif event["event_type"] in ["weekly", "monthly", "custom"]:
                await self._execute_generic_event(guild, channel, event)
        except Exception as e:
            logger.error(f"Error ejecutando evento {event['id']}: {e}")
    
    async def _execute_drop_event(self, guild, channel, event):
        """Evento tipo drop (regalo aleatorio)"""
        rewards = json.loads(event["rewards"])
        rewards_config = json.loads(event["rewards_config"]) if event["rewards_config"] else {}
        
        embed = discord.Embed(
            title="🎁 ¡Drop Aleatorio!",
            description=event["description"] or "¡Ha aparecido un drop! Reacciona con 🎁 para participar.",
            color=0xFFD700,
            timestamp=discord.utils.utcnow()
        )
        
        # Determinar ganadores
        participation_reward = rewards_config.get("participation", {})
        winner_count = rewards_config.get("winners", 1)
        
        embed.add_field(name="🎁 Premio", value=rewards.get("description", "Sorpresa"), inline=False)
        embed.add_field(name="🏆 Ganadores", value=str(winner_count), inline=True)
        embed.add_field(name="⏰ Tiempo", value="30 segundos", inline=True)
        
        msg = await channel.send(embed=embed)
        await msg.add_reaction("🎁")
        
        # Esperar 30s
        await asyncio.sleep(30)
        
        # Obtener participantes
        try:
            msg = await channel.fetch_message(msg.id)
            reaction = discord.utils.get(msg.reactions, emoji="🎁")
            if reaction:
                users = await reaction.users().flatten()
                participants = [u for u in users if not u.bot]
                
                if participants:
                    winners = random.sample(participants, min(len(participants), winner_count))
                    
                    # Dar recompensas
                    for winner in winners:
                        # Dar roles/items según config
                        pass
                    
                    # Anunciar ganadores
                    embed = discord.Embed(
                        title="🎉 ¡Drop Terminado!",
                        description=f"Ganadores: {', '.join(w.mention for w in winners)}",
                        color=0x00FF00
                    )
                    await channel.send(embed=embed)
                else:
                    await channel.send("😢 Nadie participó en el drop.")
        except Exception as e:
            logger.error(f"Error en drop event: {e}")
    
    async def _execute_koth_event(self, guild, channel, event):
        """Evento KOTH (King of the Hill)"""
        pass  # Implementar KOTH básico
    
    async def _execute_generic_event(self, guild, channel, event):
        """Evento genérico (anuncio + rewards)"""
        rewards = json.loads(event["rewards"])
        rewards_config = json.loads(event["rewards_config"]) if event["rewards_config"] else {}
        
        embed = discord.Embed(
            title=f"🎉 {event['name']}",
            description=event["description"],
            color=0x8B00FF,
            timestamp=discord.utils.utcnow()
        )
        
        if "role_id" in event and event["role_id"]:
            role = guild.get_role(event["role_id"])
            if role:
                embed.add_field(name="🎯 Rol", value=role.mention, inline=True)
        
        msg = await channel.send(embed=embed)
        
        # Si hay rol de mención
        if "role_id" in event and event["role_id"]:
            role = guild.get_role(event["role_id"])
            if role:
                await channel.send(f"{role.mention}", delete_after=5)

# Instancia global
auto_events_system = AutoEventsSystem()