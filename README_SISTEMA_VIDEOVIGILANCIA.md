# MANUAL DE USUARIO Y DOCUMENTACIÓN TÉCNICA
## Sistema de Videovigilancia IP

**Última actualización:** 30/08/2026  
**Alcance:** Red, NVR, inventario de cámaras, herramientas y procedimientos de administración e incidencias.

---

## 1. Descripción General del Sistema

El sistema de videovigilancia IP consta de:

- **1 NVR Hikvision (DS-7616NXI-K1)**: Grabador y gestor principal de hasta 16 canales.
- **6 Cámaras IP Conectadas** (Todos los canales activos y **100% ONLINE**):
  - 2 Cámaras Hikvision (Ascensores Este y Oeste).
  - 1 Cámara EZVIZ (Interior).
  - 3 Cámaras Dahua (Exteriores, Sótano y Pasillos).
- **Infraestructura de Red**: Router TP-Link Archer AX75 + FortiGate 100F. Toda la red activa opera en la subred **`192.168.1.x`**.

---

## 2. Topología de Red

```text
Internet
   │
[FortiGate 100F]   LAN Principal: 192.168.100.99  (Residuos en 192.168.0.99)
   │
[Switch TP-Link 192.168.100.114]
   │
[TP-Link Archer AX75] (Router Principal + WiFi)
   ├── WAN: 192.168.100.133
   ├── LAN: 192.168.1.1  (DHCP activo en 192.168.1.x)
   └── WiFi: "CAMSEGURIDAD"
         └── PC de Trabajo (192.168.1.x) + Teléfonos
```

| Subred | Uso y Estado |
|---|---|
| **192.168.100.x** | LAN principal (FortiGate, switch, WAN del AXE75) |
| **192.168.1.x** | **Red de trabajo activa** (NVR, cámaras, PC, DHCP) |
| **192.168.0.x** | Subred antigua / obsoleta (en proceso de migración total) |

---

## 3. Inventario de Equipos y Credenciales

### Grabador NVR (Cerebro del Sistema)
| Campo | Valor |
|---|---|
| **Modelo** | Hikvision DS-7616NXI-K1 |
| **IP** | **`192.168.1.163`** |
| **MAC** | `dc-07-f8-b4-8f-b6` |
| **Usuario / Clave** | `admin` / `*high7600#%` |
| **Nombre de Equipo** | VIGILANTE DIGITAL |

### Cámaras Conectadas al NVR (Estado al 30/08/2026)

| Canal | Nombre Canal | IP Actual | Modelo / Marca | Protocolo NVR | Credenciales Directas | Estado |
|---|---|---|---|---|---|---|
| **1** | IPCamera 01 | `192.168.1.137` | EZVIZ CS-H4-R201 | HIKVISION (8000) | `admin` / `DVPXCD` | **ONLINE** (`connect`) |
| **2** | Ascensor Oeste | `192.168.1.4` | Hikvision DS-2CD1043G2 | HIKVISION (8000) | NVR Managed | **ONLINE** (`connect`) |
| **3** | Ascensor Este | `192.168.1.3` | Hikvision DS-2CD1043G2 | HIKVISION (8000) | NVR Managed | **ONLINE** (`connect`) |
| **4** | IPCamera 04 | `192.168.1.206` | Dahua IPC-HFW4421S | ONVIF (80) | NVR Managed | **ONLINE** (`connect`) |
| **5** | Sotano Berimer | `192.168.1.14` | Dahua "IP Camera" | ONVIF (80) | `admin` / `admin` | **ONLINE** (`connect`) |
| **6** | IPCamera 06 | `192.168.1.92` | Dahua IPC-HDW1200S | ONVIF (80) | `admin` / `admin` | **ONLINE** (`connect`) |

> **Nota de Seguridad:** Las claves de las cámaras EZVIZ vienen impresas en la etiqueta del dispositivo como "Verification Code".

---

## 4. Acceso y Administración del Sistema

### 4.1 Visualización Web y Aplicaciones
- **Navegador Web:** `http://192.168.1.163` → Usuario: `admin` | Clave: `*high7600#%`
- **App Móvil / PC:** **Hik-Connect** / **iVMS-4200** apuntando a la IP `192.168.1.163`.

### 4.2 Acceso Técnico por API ISAPI (HTTP/Digest)
El NVR responde a comandos ISAPI. Ejemplos de uso rápido desde PowerShell o CMD:

```bash
# Consultar información del equipo NVR
curl -k --digest -u "admin:*high7600#%" http://192.168.1.163/ISAPI/System/deviceInfo

# Consultar estado de todos los canales
curl -k --digest -u "admin:*high7600#%" http://192.168.1.163/ISAPI/ContentMgmt/InputProxy/channels/status

# Consultar configuración de un canal específico (ej. Canal 6)
curl -k --digest -u "admin:*high7600#%" http://192.168.1.163/ISAPI/ContentMgmt/InputProxy/channels/6
```

---

## 5. Herramientas de Diagnóstico

Ubicación de scripts y utilidades en el PC: `C:\Users\Ulianov\AppData\Local\Temp\opencode\`

| Herramienta | Función Principal |
|---|---|
| **SADP (`pysadp`)** | Descubrir y cambiar IP de cámaras/NVR aunque estén fuera de subred. |
| **curl** | Consultas e inyección de datos ISAPI/CGI. |
| **rtsp_auth.ps1** | Validar flujo de video y clave RTSP de cámaras individuales. |

**Comando SADP para descubrir dispositivos:**
```bash
python -X utf8 -c "from pysadp.cli import main; raise SystemExit(main())" discover --timeout 3
```

---

## 6. Procedimiento: Añadir o Reconfigurar un Canal en el NVR

Si una cámara cambia de IP o credenciales, se actualiza en el NVR mediante una petición HTTP `PUT`:

1. Crear un archivo `canal.xml` con el siguiente formato:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<InputProxyChannel version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>6</id>
<name>IPCamera 06</name>
<sourceInputPortDescriptor>
<proxyProtocol>ONVIF</proxyProtocol>
<addressingFormatType>ipaddress</addressingFormatType>
<ipAddress>192.168.1.92</ipAddress>
<managePortNo>80</managePortNo>
<srcInputPort>1</srcInputPort>
<userName>admin</userName>
<password>admin</password>
<streamType>auto</streamType>
</sourceInputPortDescriptor>
</InputProxyChannel>
```

2. Enviarlo al NVR mediante `curl` o Python:

```bash
curl -k --digest -u "admin:*high7600#%" -X PUT --data-binary "@canal.xml" -H "Content-Type: application/xml" http://192.168.1.163/ISAPI/ContentMgmt/InputProxy/channels/6
```

---

## 7. Registro de Incidencias y Mantenimiento

### 🗓️ Incidencia 30/08/2026: Restauración de Visión en Canal 6 (`192.168.1.92`)
- **Síntoma:** La cámara `IPCamera 06` aparecía registrada en el NVR pero mostraba pantalla negra sin visión (`online: false`).
- **Diagnóstico:** El ISAPI del NVR devolvió el estado `<chanDetectResult>errorUserNameOrPasswd</chanDetectResult>`. El nodo XML del canal en el NVR carecía del campo de contraseña `<password>admin</password>`.
- **Solución:** Se inyectó la configuración XML corregida con la clave ONVIF `admin` a través de `PUT /ISAPI/ContentMgmt/InputProxy/channels/6`. El estado pasó a `online: true` con `chanDetectResult: connect` y la visión fue totalmente restablecida.

### 🗓️ Histórico 05/08/2026: Migración de Subred y Normalización
- Migración de cámaras desde `192.168.0.x` a `192.168.1.x`.
- Integración de cámara EZVIZ en Canal 1 con código de verificación `DVPXCD`.
- Estabilización de los 6 canales online.

---

## 8. Consideraciones Importantes
- **Disco Local:** El NVR realiza grabación continua en su HDD interno. Verificar estado en *Configuración -> Almacenamiento*.
- **Protección Anti-Fuerza Bruta:** El NVR bloquea la IP/cuenta por **20 minutos** si se realizan múltiples intentos de autenticación fallidos.
- **Resets de Fábrica:** No resetear cámaras sin antes leer las etiquetas físicas (códigos de verificación).
