"""
Sistema de Analytics + Prometheus metrics + Grafana dashboards
"""
import time
import asyncio
from typing import Dict, List, Optional
from collections import defaultdict
from src.database import db, log_event
from src.config.ids import GUILDS

class AnalyticsCollector:
    def __init__(self):
        self.buffers = defaultdict(list)
        self.flush_interval = 30  # segundos
        self._flush_task = None
    
    async def start(self):
        """Inicia el flush periódico"""
        self._flush_task = asyncio.create_task(self._periodic_flush())
    
    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            await self._flush_buffer()
    
    async def _periodic_flush(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        if not self.buffers:
            return
        
        # Agregar eventos a DB en batch
        for guild_id, events in self.buffers.items():
            if not events:
                continue
            
            try:
                for event in events:
                    await db.execute(
                        """INSERT INTO analytics_events 
                           (guild_id, user_id, event_type, event_data, timestamp)
                           VALUES (?, ?, ?, ?, ?)""",
                        [event["guild_id"], event["user_id"], event["event_type"],
                         event["event_data"], event["timestamp"]]
                    )
                
                # Actualizar agregados diarios/horarios
                await self._update_aggregates(events)
            
            self.buffers.clear()
    
    async def _update_aggregates(self, events: List[dict]):
        now = int(time.time() * 1000)
        date_str = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        hour_str = time.strftime("%Y-%m-%d-%H", time.localtime(time.time()))
        
        # Contar por tipo de evento
        counts = {}
        for event in events:
            key = f"{event['guild_id']}:{event['event_type']}"
            counts[key] = counts.get(key, 0) + 1
        
        # Actualizar daily
        for key, count in counts.items():
            guild_id, metric = key.split(":", 1)
            date_str = time.strftime("%Y-%m-%d")
            await db.execute(
                """INSERT INTO analytics_daily (guild_id, date, metric, value)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(guild_id, date, metric) DO UPDATE SET value = value + excluded.value""",
                [int(guild_id), date_str, metric, count]
            )
            
            # Hourly
            hour_str = time.strftime("%Y-%m-%d-%H")
            await db.execute(
                """INSERT INTO analytics_hourly (guild_id, hour, metric, value)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(guild_id, hour, metric) DO UPDATE SET value = value + excluded.value""",
                [guild_id, time.strftime("%Y-%m-%d-%H"), metric, count]
            )
    
    def track(self, guild_id: int, user_id: str, event_type: str, data: dict = None):
        """Registra un evento"""
        event = {
            "guild_id": guild_id,
            "user_id": user_id,
            "event_type": event_type,
            "event_data": json.dumps(data) if data else "{}",
            "timestamp": int(time.time() * 1000)
        }
        self.buffers[guild_id].append(event)

# Prometheus Metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Métricas globales
COMMANDS_TOTAL = Counter('aegox_commands_total', 'Total commands executed', ['command', 'guild_id', 'status'])
COMMAND_LATENCY = Histogram('aegox_command_latency_seconds', 'Command latency', ['command'])
ACTIVE_USERS = Gauge('aegox_active_users', 'Active users', ['guild_id'])
GUILD_MEMBERS = Gauge('aegox_guild_members', 'Guild members', ['guild_id'])
ACTIVE_GIVEAWAYS = Gauge('aegox_active_giveaways', 'Active giveaways', ['guild_id'])
PENDING_APPLICATIONS = Gauge('aegox_pending_applications', 'Pending applications', ['guild_id', 'type'])
DB_QUERY_LATENCY = Histogram('aegox_db_latency_seconds', 'Database query latency', ['operation'])
ANTI_ALT_DETECTIONS = Counter('aegox_anti_alt_detections_total', 'Anti-alt detections', ['guild_id', 'type', 'risk_level'])
TICKETS_CREATED = Counter('aegox_tickets_created_total', 'Tickets created', ['guild_id', 'category'])
TICKETS_CLOSED = Counter('aegox_tickets_closed_total', 'Tickets closed', ['guild_id', 'category'])
VERIFICATIONS = Counter('aegox_verifications_total', 'Web verifications', ['guild_id', 'success'])
ANTI_ALT_DETECTIONS = Counter('aegox_anti_alt_detections_total', 'Anti-alt detections', ['guild_id', 'risk_level'])

# Helpers para tracking
def track_command(command: str, guild_id: int, status: str = "success"):
    COMMANDS_TOTAL.labels(command=command, guild_id=str(guild_id), status=status).inc()

def track_latency(command: str, latency: float):
    COMMAND_LATENCY.labels(command=command).observe(latency)

def track_db_query(operation: str, latency: float):
    DB_QUERY_LATENCY.labels(operation=operation).observe(latency)

def track_anti_alt_detection(guild_id: int, risk_level: str):
    ANTI_ALT_DETECTIONS.labels(guild_id=str(guild_id), risk_level=risk_level).inc()

def track_ticket_created(guild_id: int, category: str):
    TICKETS_CREATED.labels(guild_id=str(guild_id), category=category).inc()

def track_ticket_closed(guild_id: int, category: str):
    TICKETS_CLOSED.labels(guild_id=str(guild_id), category=category).inc()

def track_verification(guild_id: int, success: bool):
    VERIFICATIONS.labels(guild_id=str(guild_id), success=str(success).lower()).inc()

# Metrics endpoint para Prometheus
async def metrics_endpoint(request):
    from starlette.responses import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Instancia global
analytics_collector = AnalyticsCollector()