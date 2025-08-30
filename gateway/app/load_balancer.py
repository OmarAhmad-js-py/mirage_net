import aiohttp
import asyncio
import random
import time
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
import os

logger = logging.getLogger("mirage-load-balancer")

@dataclass
class PeerHealth:
    peer_id: str
    ip_address: str
    last_seen: float
    response_time: float  # in milliseconds
    active_connections: int
    max_connections: int
    success_rate: float   # value between 0-1.0

class LoadAwareBalancer:
    def __init__(self):
        self.peer_health: Dict[str, PeerHealth] = {}
        self.controller_url = f"http://{os.getenv('CN_HOST')}:{os.getenv('CN_PORT')}/api/v1/peer/list"
        self.api_key = os.getenv('CN_API_KEY')
        self.update_interval = 30  # seconds
        self._update_task = None

    async def start(self):
        """Start background health update task"""
        self._update_task = asyncio.create_task(self._update_peer_health_loop())
        logger.info("Load balancer started")

    async def stop(self):
        """Stop background health update task"""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    async def _update_peer_health_loop(self):
        """Continuously update peer health metrics"""
        while True:
            try:
                await self._fetch_peer_health()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health update loop error: {e}")
                await asyncio.sleep(10)


    async def _fetch_peer_health(self):
        """Fetch peer list from controller with retry logic"""
        max_retries = 5
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.controller_url, 
                        headers={'X-API-Key': self.api_key},
                        timeout=10
                    ) as response:
                        
                        if response.status == 200:
                            data = await response.json()
                            peers = data.get('peers', [])
                            
                            for peer in peers:
                                peer_id = peer['id']
                                if peer_id not in self.peer_health:
                                    # New peer - initialize health data
                                    self.peer_health[peer_id] = PeerHealth(
                                        peer_id=peer_id,
                                        ip_address=peer['ip'],
                                        last_seen=time.time(),
                                        response_time=100.0,
                                        active_connections=0,
                                        max_connections=50,
                                        success_rate=0.95
                                    )
                                else:
                                    # Update existing peer's last seen
                                    self.peer_health[peer_id].last_seen = time.time()
                            
                            # Remove stale peers
                            stale_time = time.time() - 300
                            stale_peers = [
                                pid for pid, health in self.peer_health.items() 
                                if health.last_seen < stale_time
                            ]
                            for pid in stale_peers:
                                del self.peer_health[pid]
                            
                            logger.info(f"Successfully updated health for {len(peers)} peers")
                            return
                        else:
                            logger.warning(f"Controller returned status {response.status}, attempt {attempt+1}/{max_retries}")
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to fetch peer health (attempt {attempt+1}/{max_retries}): {e}")
                    await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch peer health after {max_retries} attempts: {e}")


    def update_peer_performance(self, peer_id: str, response_time: float, success: bool):
        """Update peer performance metrics after a request"""
        if peer_id in self.peer_health:
            health = self.peer_health[peer_id]
            
            # Update response time with exponential moving average
            health.response_time = 0.7 * health.response_time + 0.3 * response_time
            
            # Update success rate
            if success:
                health.success_rate = min(1.0, health.success_rate + 0.01)
            else:
                health.success_rate = max(0.0, health.success_rate - 0.05)
            
            # Update connection count
            if success:
                health.active_connections += 1
                # Schedule connection count decrement after assumed request completion
                asyncio.create_task(self._decrement_connection_count(peer_id, 60))

    async def _decrement_connection_count(self, peer_id: str, delay: int):
        """Decrement connection count after delay"""
        await asyncio.sleep(delay)
        if peer_id in self.peer_health:
            self.peer_health[peer_id].active_connections = max(
                0, self.peer_health[peer_id].active_connections - 1
            )

    def get_best_peer(self) -> Optional[PeerHealth]:
        """Select best peer based on load and performance metrics"""
        available_peers = [
            health for health in self.peer_health.values() 
            if health.active_connections < health.max_connections
            and health.success_rate > 0.7  # Minimum success rate threshold
        ]
        
        if not available_peers:
            return None
        
        # Score peers based on multiple factors
        scored_peers = []
        for peer in available_peers:
            # Calculate load factor (0-1, lower is better)
            load_factor = peer.active_connections / peer.max_connections
            
            # Calculate performance score (higher is better)
            performance_score = (1000 / peer.response_time) * peer.success_rate
            
            # Combine scores (weight performance higher than load)
            total_score = (0.3 * (1 - load_factor)) + (0.7 * performance_score)
            
            scored_peers.append((total_score, peer))
        
        # Select peer with highest score
        scored_peers.sort(key=lambda x: x[0], reverse=True)
        return scored_peers[0][1] if scored_peers else None

    def get_peer_by_id(self, peer_id: str) -> Optional[PeerHealth]:
        """Get specific peer health data"""
        return self.peer_health.get(peer_id)