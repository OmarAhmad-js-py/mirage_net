from fastapi import FastAPI, Header, HTTPException, status
import uvicorn
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
import netaddr

from database import RedisDB
from peer_manager import PeerManager
from security import validate_api_key, encrypt_data, decrypt_data

app = FastAPI(title="Mirage-Net Controller", docs_url=None, redoc_url=None)
db = RedisDB()
peer_manager = PeerManager(db)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mirage-controller")

@app.post("/api/v1/peer/register")
async def register_peer(peer_data: dict, x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    try:
        peer_id = peer_data.get("peer_id")
        ip_address = peer_data.get("ip")
        capabilities = peer_data.get("capabilities", {})
        
        if not all([peer_id, ip_address]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields")
        
        peer_info = {
            "id": peer_id,
            "ip": ip_address,
            "capabilities": capabilities,
            "last_seen": datetime.utcnow().isoformat(),
            "status": "online"
        }
        
        success = peer_manager.register_peer(peer_info)
        if success:
            logger.info(f"Peer registered: {peer_id}")
            return {"status": "success", "peer_id": peer_id}
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed")
            
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/v1/peer/list")
async def list_peers(x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    try:
        peers = peer_manager.get_available_peers()
        return {"status": "success", "peers": peers}
    except Exception as e:
        logger.error(f"List peers error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/v1/peer/heartbeat")
async def peer_heartbeat(heartbeat_data: dict, x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    try:
        peer_id = heartbeat_data.get("peer_id")
        if not peer_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Peer ID required")
        
        success = peer_manager.update_peer_heartbeat(peer_id)
        if success:
            return {"status": "success"}
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Peer not found")
            
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/v1/network/status")
async def network_status(x_api_key: str = Header(...)):
    if not validate_api_key(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    
    try:
        stats = peer_manager.get_network_stats()
        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")