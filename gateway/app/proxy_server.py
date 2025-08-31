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
        
        @web.middleware
        async def catch_all_middleware(request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]) -> web.StreamResponse:
            # Handle CONNECT requests here before routing
            if request.method == 'CONNECT':
                logger.info(f"Middleware caught CONNECT: {request.path}")
                response = web.Response(status=200)
                response.force_close()
                return response
            return await handler(request)
    
    self.app.middlewares.append(catch_all_middleware)

        # Add all routes explicitly
        self.app.router.add_route('GET', '/{path:.*}', self.handle_request)
        self.app.router.add_route('POST', '/{path:.*}', self.handle_request)
        self.app.router.add_route('PUT', '/{path:.*}', self.handle_request)
        self.app.router.add_route('DELETE', '/{path:.*}', self.handle_request)
        self.app.router.add_route('CONNECT', '/{path:.*}', self.handle_request)  # Explicit CONNECT

        # Debug: Print registered routes
        print("Registered routes:")
        for resource in self.app.router.resources():
            for route in resource:
                print(f"  {route.method} -> {route.handler}")

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

    async def direct_connection(self, request: web.Request, target_url: str) -> web.Response:
        """Fallback direct connection without proxy"""
        try:
            async with ClientSession() as session:
                async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=dict(request.headers),
                    data=await request.read() if request.can_read_body else None,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_data = await response.read()
                    return web.Response(
                        status=response.status,
                        body=response_data,
                        headers=dict(response.headers)
                    )
        except Exception as e:
            logger.error(f"Direct connection failed: {e}")
            return web.Response(status=502, text="Direct connection failed")

    async def handle_connect_request(self, request: web.Request) -> web.Response:
        """Handle HTTPS CONNECT requests"""
        logger.info(f"HTTPS CONNECT request for: {request.path}")

        # Return 200 to allow HTTPS tunnel establishment
        response = web.Response(status=200)
        response.force_close()
        return response

    async def handle_request(self, request: web.Request) -> web.Response:
        try:
            full_path = request.path_qs
            logger.info(f"Received {request.method} request: {full_path}")

            # Handle CONNECT requests (HTTPS tunneling)
            if request.method == 'CONNECT':
                # Check if path is empty (malformed request)
                if not request.path or request.path == '/':
                    logger.warning("Empty CONNECT request - returning 200 anyway")
                    response = web.Response(status=200)
                    response.force_close()
                    return response

                logger.info(f"CONNECT request for: {request.path}")
                # Return 200 to establish tunnel
                response = web.Response(status=200)
                response.force_close()
                return response

            # Handle Twitch security requests
            if 'time/1/current' in full_path or 'cup2key' in full_path:
                logger.info(f"Twitch security request: {full_path}")
                # Return empty 200 response
                return web.Response(status=200, text="")

            # Handle all other requests
            logger.info(f"Regular request: {full_path}")
            return web.Response(status=200, text="OK")

        except Exception as e:
            logger.error(f"Handler error: {e}")
            return web.Response(status=500, text=str(e))
  # async def handle_request(self, request: web.Request) -> web.Response:
    #    # Handle CONNECT requests first
    #     if request.method == 'CONNECT':
    #         return await self.handle_connect_request(request)
        
    #     # EXTRACT THE COMPLETE URL PROPERLY
    #     # Get the full path including query parameters
    #     full_path = request.path_qs
        
    #     # Check if this is a Twitch security request (special handling)
    #     if 'time/1/current' in full_path or 'cup2key' in full_path:
    #         # These are Twitch's anti-bot requests - they need to go to the actual Twitch domain
    #         target_url = f"https://www.twitch.tv{full_path}"
    #         logger.info(f"Twitch security request to: {target_url}")
    #         return await self.direct_connection(request, target_url)
    #         return web.Response(status=200, text="")
        
    #     # For regular requests, reconstruct the proper URL
    #     if full_path.startswith('/'):
    #         full_path = full_path[1:]  # Remove leading slash
        
    #     # Ensure it's a complete URL with domain
    #     if not full_path.startswith(('http://', 'https://')):
    #         # Assume it's a Twitch URL
    #         target_url = f"https://www.twitch.tv/{full_path}"
    #     else:
    #         target_url = full_path
        
    #     logger.info(f"Proxying request to: {target_url}")
        
    #     # Try to use proxy peers if available
    #     peer = self.load_balancer.get_best_peer()
    #     if not peer:
    #         logger.warning("No peers available, using direct connection")
    #         return await self.direct_connection(request, target_url)
        
        
    #     try:
    #         peer = self.load_balancer.get_best_peer()
    #         if not peer:
    #             return web.Response(status=502, text="No available peers")
            
    #         start_time = time.time()
    #         success = False
            
    #         try:
    #             async with ClientSession(
    #                 connector=ProxyConnector.from_url(f"socks5://{peer.ip_address}:1080")
    #             ) as session:
    #                 async with session.request(
    #                     method=request.method,
    #                     url=target_url,
    #                     headers=dict(request.headers),
    #                     data=await request.read() if request.can_read_body else None,
    #                     timeout=aiohttp.ClientTimeout(total=30)
    #                 ) as response:
    #                     response_data = await response.read()
    #                     success = True
    #                     return web.Response(
    #                         status=response.status,
    #                         body=response_data,
    #                         headers=dict(response.headers)
    #                 )
    #         finally:
    #             # Update peer performance metrics
    #             response_time = (time.time() - start_time) * 1000  # convert to ms
    #             self.load_balancer.update_peer_performance(peer.peer_id, response_time, success)
                    
    #     except asyncio.TimeoutError:
    #         logger.warning(f"Request timeout: {target_url}")
    #         return web.Response(status=504, text="Gateway timeout")
    #     except Exception as e:
    #         logger.error(f"Proxy error: {e}")
    #         return await self.direct_connection(request, target_url)
        