"""
Sistema Anti-Alt: Detección de cuentas alternativas
IP matching, HWID, fingerprinting, behavioral analysis, ML scoring
"""
import hashlib
import json
import time
import random
from typing import Dict, List, Optional, Tuple
from src.database import db, get_setting, log_event
from src.config.ids import ROLES, CHANNELS

class AntiAltDetector:
    def __init__(self):
        self.whitelisted_ips = set()
        self.suspicious_threshold = 0.7
        self.auto_action_threshold = 0.85
    
    async def analyze_user(self, guild_id: int, user_id: str, 
                          ip: str = None, hwid: str = None,
                          browser_fp: str = None, user_agent: str = None) -> dict:
        """Analiza un usuario y retorna score de riesgo"""
        results = {
            "user_id": user_id,
            "guild_id": guild_id,
            "risk_score": 0.0,
            "risk_level": "low",
            "detections": [],
            "matched_users": [],
            "action": "none"
        }
        
        # 1. IP Reputation Check
        if ip:
            ip_result = await self._check_ip(guild_id, ip)
            if ip_result["suspicious"]:
                results["detections"].append({
                    "type": "ip_reputation",
                    "confidence": ip_result["confidence"],
                    "details": ip_result
                })
                results["risk_score"] = max(results["risk_score"], ip_result["confidence"])
            
            # IP Match con otros usuarios
            matches = await self._find_ip_matches(guild_id, ip, exclude_user=user_id)
            if matches:
                results["detections"].append({
                    "type": "ip_match",
                    "confidence": 0.8,
                    "matched_users": matches
                })
                results["matched_users"].extend(matches)
        
        # 2. HWID Match
        if hwid:
            matches = await self._find_hwid_matches(guild_id, hwid, exclude_user=user_id)
            if matches:
                results["detections"].append({
                    "type": "hwid_match",
                    "confidence": 0.9,
                    "matched_users": matches
                })
                results["matched_users"].extend(matches)
        
        # 3. Browser Fingerprint Match
        if browser_fp:
            matches = await self._find_fingerprint_matches(guild_id, browser_fp, exclude_user=user_id)
            if matches:
                results["detections"].append({
                    "type": "fingerprint_match",
                    "confidence": 0.75,
                    "matched_users": matches
                })
                results["matched_users"].extend(matches)
        
        # 4. Behavioral Analysis
        behavioral = await self._analyze_behavior(user_id, guild_id)
        if behavioral["anomalous"]:
            results["detections"].append({
                "type": "behavioral_anomaly",
                "confidence": behavioral["confidence"],
                "details": behavioral
            })
            results["risk_score"] = max(results["risk_score"], behavioral["confidence"])
        
        # 5. ML Score (si modelo entrenado)
        ml_score = await self._get_ml_score(user_id, guild_id)
        if ml_score > 0:
            results["detections"].append({
                "type": "ml_score",
                "confidence": ml_score,
                "details": {"score": ml_score}
            })
            results["risk_score"] = max(results["risk_score"], ml_score)
        
        # Determinar nivel de riesgo y acción
        results["risk_score"] = min(results["risk_score"], 1.0)
        results["risk_level"] = self._get_risk_level(results["risk_score"])
        results["action"] = self._determine_action(results["risk_level"])
        results["matched_users"] = list(set(results["matched_users"]))
        
        # Guardar detección si hay riesgo
        if results["risk_score"] > 0.3:
            await self._save_detection(guild_id, user_id, results)
        
        return results
    
    async def _check_ip(self, guild_id: int, ip: str) -> dict:
        from src.database import db
        result = await db.fetchone(
            "SELECT * FROM ip_reputation WHERE ip = ? AND guild_id = ?",
            [ip, guild_id]
        )
        
        if not result:
            # Verificar si es VPN/Proxy/Tor (usar API externa)
            vpn_check = await self._check_vpn_proxy(ip)
            return {
                "suspicious": vpn_check["is_vpn"] or vpn_check["is_tor"] or vpn_check["is_datacenter"],
                "confidence": 0.6 if (vpn_check["is_vpn"] or vpn_check["is_tor"]) else 0.1,
                "details": vpn_check
            }
        
        suspicious = (
            result["reputation"] < -50 or
            result["vpn_proxy"] or result["tor"] or result["datacenter"] or
            result["alt_count"] > 3
        )
        
        return {
            "suspicious": suspicious,
            "confidence": 0.8 if suspicious else 0.1,
            "details": dict(result)
        }
    
    async def _check_vpn_proxy(self, ip: str) -> dict:
        # Aquí iría llamada a API externa (ipapi.co, ipqualityscore, etc)
        # Por ahora retorno mock
        return {
            "is_vpn": False,
            "is_proxy": False,
            "is_tor": False,
            "is_datacenter": False,
            "country": "AR",
            "asn": "AS12345"
        }
    
    async def _find_ip_matches(self, guild_id: int, ip: str, exclude_user: str) -> List[str]:
        from src.database import db
        result = await db.fetchall(
            "SELECT DISTINCT user_id FROM user_fingerprints WHERE guild_id = ? AND ip_history LIKE ? AND user_id != ?",
            [guild_id, f"%{ip}%", exclude_user]
        )
        return [r["user_id"] for r in result]
    
    async def _find_hwid_matches(self, guild_id: int, hwid: str, exclude_user: str) -> List[str]:
        from src.database import db
        result = await db.fetchall(
            "SELECT user_id FROM user_fingerprints WHERE guild_id = ? AND hwids LIKE ? AND user_id != ?",
            [guild_id, f"%{hwid}%", exclude_user]
        )
        return [r["user_id"] for r in result]
    
    async def _find_fingerprint_matches(self, guild_id: int, fp: str, exclude_user: str) -> List[str]:
        from src.database import db
        result = await db.fetchall(
            "SELECT user_id FROM user_fingerprints WHERE guild_id = ? AND browser_fingerprints LIKE ? AND user_id != ?",
            [guild_id, f"%{fp}%", exclude_user]
        )
        return [r["user_id"] for r in result]
    
    async def _analyze_behavior(self, user_id: str, guild_id: int) -> dict:
        from src.database import db
        fp = await db.fetchone(
            "SELECT * FROM user_fingerprints WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id]
        )
        
        if not fp or not fp["behavioral_data"]:
            return {"anomalous": False, "confidence": 0}
        
        try:
            data = json.loads(fp["behavioral_data"])
        except:
            return {"anomalous": False, "confidence": 0}
        
        anomalies = []
        confidence = 0
        
        # Verificar patrones sospechosos
        if data.get("avg_msg_len", 0) < 5:
            anomalies.append("Mensajes muy cortos (posible bot)")
            confidence += 0.2
        
        if data.get("commands_per_min", 0) > 10:
            anomalies.append("Demasiados comandos por minuto")
            confidence += 0.3
        
        active_hours = data.get("active_hours", [])
        if len(set(active_hours)) < 3 and sum(data.get("hourly_counts", {}).values()) > 100:
            anomalies.append("Actividad en pocas horas (posible bot)")
            confidence += 0.3
        
        if data.get("cmd_diversity", 0) < 3 and data.get("total_commands", 0) > 50:
            anomalies.append("Poca diversidad de comandos")
            confidence += 0.2
        
        return {
            "anomalous": len(anomalies) > 0,
            "confidence": min(confidence, 1.0),
            "anomalies": anomalies
        }
    
    async def _get_ml_score(self, user_id: str, guild_id: int) -> float:
        from src.database import db
        fp = await db.fetchone(
            "SELECT ml_score FROM user_fingerprints WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id]
        )
        return fp["ml_score"] if fp else 0.0
    
    def _get_risk_level(self, score: float) -> str:
        if score >= 0.85:
            return "critical"
        elif score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        return "low"
    
    def _determine_action(self, risk_level: str) -> str:
        actions = {
            "critical": "ban_and_alert",
            "high": "quarantine_and_alert",
            "medium": "flag_and_monitor",
            "low": "monitor"
        }
        return actions.get("low", "monitor")
    
    async def _save_detection(self, guild_id: int, user_id: str, results: dict):
        from src.database import db
        await db.execute(
            """INSERT INTO alt_detections 
               (user_id, guild_id, ip, hwid, browser_fingerprint, detection_type, 
                confidence, matched_user_id, evidence, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                user_id, guild_id,
                results.get("ip"), results.get("hwid"), results.get("browser_fp"),
                ",".join([d["type"] for d in results["detections"]]),
                results["risk_score"],
                json.dumps(results["matched_users"]),
                json.dumps([d for d in results["detections"]]),
                "pending",
                int(time.time() * 1000)
            ]
        )

    async def register_user_fingerprint(self, guild_id: int, user_id: str,
                                       ip: str = None, hwid: str = None,
                                       browser_fp: str = None, user_agent: str = None):
        """Registra/actualiza fingerprint de usuario"""
        from src.database import db
        
        existing = await db.fetchone(
            "SELECT * FROM user_fingerprints WHERE user_id = ? AND guild_id = ?",
            [user_id, guild_id]
        )
        
        ip_history = [ip] if ip else []
        hwids = [hwid] if hwid else []
        fingerprints = [self._hash_fingerprint(user_agent)] if user_agent else []
        
        if existing:
            try:
                old_ips = json.loads(existing["ip_history"]) if existing["ip_history"] else []
                old_hwids = json.loads(existing["hwids"]) if existing["hwids"] else []
                old_fps = json.loads(existing["browser_fingerprints"]) if existing["browser_fingerprints"] else []
            except:
                old_ips, old_hwids, old_fps = [], [], []
            
            if ip and ip not in old_ips:
                old_ips.append(ip)
            if hwid and hwid not in old_hwids:
                old_hwids.append(hwid)
            if user_agent and self._hash_fingerprint(user_agent) not in old_fps:
                old_fps.append(self._hash_fingerprint(user_agent))
            
            # Mantener solo últimos 50
            ip_history = old_ips[-50:]
            hwids = old_hwids[-50:]
            fingerprints = old_fps[-50:]
            
            await db.execute(
                """UPDATE user_fingerprints SET 
                   ip_history = ?, hwids = ?, browser_fingerprints = ?, last_updated = ?
                   WHERE user_id = ? AND guild_id = ?""",
                [json.dumps(ip_history), json.dumps(hwids), json.dumps(fingerprints),
                 int(time.time() * 1000), user_id, guild_id]
            )
        else:
            await db.execute(
                """INSERT INTO user_fingerprints 
                   (user_id, guild_id, ip_history, hwids, browser_fingerprints, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [user_id, guild_id, json.dumps([ip] if ip else []), 
                 json.dumps([hwid] if hwid else []), 
                 json.dumps([self._hash_fingerprint(user_agent)] if user_agent else []),
                 int(time.time() * 1000)]
            )
    
    def _hash_fingerprint(self, user_agent: str) -> str:
        return hashlib.sha256(user_agent.encode()).hexdigest()[:32]

# Instancia global
anti_alt_detector = AntiAltDetector()