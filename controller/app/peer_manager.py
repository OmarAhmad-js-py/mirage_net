from datetime import datetime, timedelta
import logging
import os
from typing import List, Dict, Any, Optional
import random

from database import RedisDB

logger = logging.getLogger("mirage-peer-manager")

class PeerManager:
    def __init__(self, db: RedisDB):
        self.db = db
        self.peer_timeout = int(os.getenv("PEER_TIMEOUT", 60))
    
    def register_peer(self, peer_info: Dict[str, Any]) -> bool:
        try:
            peer_id = peer_info["id"]
            key = f"peer:{peer_id}"
            return self.db.set_key(key, peer_info, expire=self.peer_timeout * 2)
        except Exception as e:
            logger.error(f"Register peer error: {e}")
            return False
    
    def get_peer(self, peer_id: str) -> Optional[Dict[str, Any]]:
        return self.db.get_key(f"peer:{peer_id}")
    
    def get_available_peers(self) -> List[Dict[str, Any]]:
        available_peers = []
        all_peer_keys = self.db.get_all_keys("peer:*")
        
        for key in all_peer_keys:
            peer = self.db.get_key(key)
            if peer and self._is_peer_online(peer):
                available_peers.append(peer)
        
        return available_peers
    
    def update_peer_heartbeat(self, peer_id: str) -> bool:
        peer = self.get_peer(peer_id)
        if not peer:
            return False
        
        peer["last_seen"] = datetime.utcnow().isoformat()
        key = f"peer:{peer_id}"
        return self.db.set_key(key, peer, expire=self.peer_timeout * 2)
    
    def _is_peer_online(self, peer: Dict[str, Any]) -> bool:
        try:
            last_seen = datetime.fromisoformat(peer["last_seen"])
            return (datetime.utcnow() - last_seen) < timedelta(seconds=self.peer_timeout)
        except (ValueError, KeyError):
            return False
    
    def cleanup_dead_peers(self):
        all_peer_keys = self.db.get_all_keys("peer:*")
        for key in all_peer_keys:
            peer = self.db.get_key(key)
            if peer and not self._is_peer_online(peer):
                self.db.delete_key(key)
                logger.info(f"Cleaned up dead peer: {peer['id']}")
    
    def get_network_stats(self) -> Dict[str, Any]:
        peers = self.get_available_peers()
        return {
            "total_peers": len(peers),
            "peer_ids": [peer["id"] for peer in peers],
            "timestamp": datetime.utcnow().isoformat()
        }