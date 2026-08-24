import asyncio
import json
import logging
import socket
from typing import Optional

logger = logging.getLogger("cobalto_lan_discovery")

UDP_DISCOVERY_PORT = 8084
DEFAULT_HTTP_PORT = 8083


class CobaltoLanDiscoveryDaemon:
    """
    Demonio de Autodescubrimiento Táctico LAN (Zero-Conf) para COBALTO HUB (PC).
    Escucha peticiones UDP broadcast en el puerto 8084 y responde instantáneamente
    a los dispositivos COBALTO Móvil con la IP local y puerto activo del servidor HTTP/API.
    """

    def __init__(self, http_port: int = DEFAULT_HTTP_PORT, udp_port: int = UDP_DISCOVERY_PORT):
        self.http_port = http_port
        self.udp_port = udp_port
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._listen_loop(), name="cobalto_lan_discovery_task")
        logger.info(f"📡 [LAN DISCOVERY] Demonio de autodescubrimiento activo en puerto UDP {self.udp_port}")
        return self._task

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("📡 [LAN DISCOVERY] Demonio de autodescubrimiento detenido.")

    async def _listen_loop(self):
        loop = asyncio.get_running_loop()

        # Crear Socket UDP Asíncrono no bloqueante
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        sock.setblocking(False)

        try:
            sock.bind(('0.0.0.0', self.udp_port))
        except Exception as bind_err:
            logger.warning(f"⚠️ [LAN DISCOVERY] No se pudo vincular al puerto UDP {self.udp_port}: {bind_err}")
            return

        payload_resp = json.dumps({
            "service": "COBALTO_HUB",
            "port": self.http_port,
            "name": "COBALTO-HUB-PC",
            "status": "ONLINE"
        }).encode('utf-8')

        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(sock, 1024)
                msg = data.decode('utf-8', errors='ignore')

                if 'COBALTO_DISCOVERY_PROBE' in msg:
                    await loop.sock_sendto(sock, payload_resp, addr)
                    logger.info(f"📡 [LAN DISCOVERY] Respuesta de autodescubrimiento enviada a COBALTO Móvil ({addr[0]}:{addr[1]})")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[LAN DISCOVERY] Excepción en bucle de escucha UDP: {e}")
                await asyncio.sleep(1)

        sock.close()


lan_discovery = CobaltoLanDiscoveryDaemon()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    print("🚀 Iniciando Demonio Standalone de Autodescubrimiento Táctico COBALTO HUB...")
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(lan_discovery.start())
        loop.run_forever()
    except KeyboardInterrupt:
        print("\n⏹️ Deteniendo Demonio de Autodescubrimiento...")
        lan_discovery.stop()
