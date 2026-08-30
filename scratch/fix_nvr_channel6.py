import requests
from requests.auth import HTTPDigestAuth
import time

ip = '192.168.1.163'
auth = HTTPDigestAuth('admin', '*high7600#%')

xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
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
</InputProxyChannel>"""

print('=== 1. Sending PUT to update Channel 6 XML ===')
r = requests.put(
    f'http://{ip}/ISAPI/ContentMgmt/InputProxy/channels/6',
    data=xml_payload.encode('utf-8'),
    headers={'Content-Type': 'application/xml'},
    auth=auth,
    timeout=5
)
print('PUT Response Status Code:', r.status_code)
print('PUT Response Text:\n', r.text)

print('\nWaiting 3 seconds for NVR to re-establish connection...')
time.sleep(3)

print('=== 2. Checking Channel 6 Status ===')
r_status = requests.get(
    f'http://{ip}/ISAPI/ContentMgmt/InputProxy/channels/6/status',
    auth=auth,
    timeout=5
)
print('Status Code:', r_status.status_code)
print('Status XML:\n', r_status.text)

print('\n=== 3. Checking All 6 Channels Final Status ===')
r_all = requests.get(
    f'http://{ip}/ISAPI/ContentMgmt/InputProxy/channels/status',
    auth=auth,
    timeout=5
)
print('All Channels XML:\n', r_all.text)
