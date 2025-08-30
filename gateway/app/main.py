from proxy_server import ProxyServer
import asyncio
import logging
import os
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mirage-gateway")

async def main():
    # Wait for controller to be fully ready (5-second delay)
    logger.info("Waiting for controller initialization...")
    await asyncio.sleep(5)
    
    gateway_host = os.getenv("GN_HOST", "0.0.0.0")
    gateway_port = int(os.getenv("GN_PORT", 8080))
    
    server = ProxyServer()
    await server.start_server(gateway_host, gateway_port)
    
    try:
        logger.info(f"Mirage-Net Gateway running on {gateway_host}:{gateway_port}")
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down gateway...")
    finally:
        await server.stop_server()

if __name__ == "__main__":
    asyncio.run(main())