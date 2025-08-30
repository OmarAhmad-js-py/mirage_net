from aiohttp import web, ClientSession, TCPConnector
from aiohttp_socks import ProxyConnector
import aiohttp
import asyncio
import logging
import time
from typing import Optional, Dict, Any
import requests

from load_balancer import LoadAwareBalancer

logger = logging.getLogger("mirage-proxy")

class ProxyServer:
    def __init__(self):
        self.app = web.Application()
        self.app.router.add_route('GET', '/{path:.*}', self.handle_request)
        self.app.router.add_route('POST', '/{path:.*}', self.handle_request)
        self.app.router.add_route('PUT', '/{path:.*}', self.handle_request)
        self.app.router.add_route('DELETE', '/{path:.*}', self.handle_request)
        self.runner = None
        self.site = None
        self.load_balancer = LoadAwareBalancer()
    
    async def start_server(self, host: str, port: int):
        await self.load_balancer.start()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, host, port)
        await self.site.start()
    
    async def stop_server(self):
        await self.load_balancer.stop()
        if self.runner:
            await self.runner.cleanup()
    
    async def handle_request(self, request: web.Request) -> web.Response:
        target_url = str(request.url).split('/', 3)[3]
        target_url = f"https://{target_url}"
        
        logger.info(f"Incoming request for: {target_url}")
        
        try:
            peer = self.load_balancer.get_best_peer()
            if not peer:
                return web.Response(status=502, text="No available peers")
            
            start_time = time.time()
            success = False
            
            try:
                async with ClientSession(
                    connector=ProxyConnector.from_url(f"socks5://{peer.ip_address}:1080")
                ) as session:
                    async with session.request(
                        method=request.method,
                        url=target_url,
                        headers=dict(request.headers),
                        data=await request.read() if request.can_read_body else None,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        response_data = await response.read()
                        success = True
                        return web.Response(
                            status=response.status,
                            body=response_data,
                            headers=dict(response.headers)
                    )
            finally:
                # Update peer performance metrics
                response_time = (time.time() - start_time) * 1000  # convert to ms
                self.load_balancer.update_peer_performance(peer.peer_id, response_time, success)
                    
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout: {target_url}")
            return web.Response(status=504, text="Gateway timeout")
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            return web.Response(status=500, text=str(e))