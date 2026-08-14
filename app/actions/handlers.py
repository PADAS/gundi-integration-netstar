import uuid
import re
import httpx
import xml.etree.ElementTree as ET

from app.services.activity_logger import activity_logger
from app.services.gundi import send_observations_to_gundi
from .configurations import NetstarAuthConfig, NetstarPullObservationsConfig

NETSTAR_URL = "https://profleet.netstar.co.za/avmportal/VehicleActivity.asmx"


def _get_text(element, tag, default=None):
    node = element.find(tag)
    return node.text if node is not None else default


@activity_logger()
async def action_auth(integration, action_config: NetstarAuthConfig):
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <GetVehicleLocations xmlns="PinpointComms.WebServices">
          <Request>
            <Credentials>
              <UserName>{action_config.username}</UserName>
              <Password>{action_config.password.get_secret_value()}</Password>
            </Credentials>
            <RequestId>{str(uuid.uuid4())}</RequestId>
            <Compress>false</Compress>
            <Reset>false</Reset>
          </Request>
        </GetVehicleLocations>
      </soap:Body>
    </soap:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"PinpointComms.WebServices/GetVehicleLocations"',
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(NETSTAR_URL, content=soap_body, headers=headers)
        response.raise_for_status()

    return {"valid_credentials": True}


@activity_logger()
async def action_pull_observations(integration, action_config: NetstarPullObservationsConfig):
    reset_value = "true" if action_config.reset else "false"
    soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <GetVehicleLocations xmlns="PinpointComms.WebServices">
          <Request>
            <Credentials>
              <UserName>{action_config.username}</UserName>
              <Password>{action_config.password.get_secret_value()}</Password>
            </Credentials>
            <RequestId>{str(uuid.uuid4())}</RequestId>
            <Compress>false</Compress>
            <Reset>{reset_value}</Reset>
          </Request>
        </GetVehicleLocations>
      </soap:Body>
    </soap:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"PinpointComms.WebServices/GetVehicleLocations"',
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(NETSTAR_URL, content=soap_body, headers=headers)
        response.raise_for_status()

    clean_xml = re.sub(' xmlns="[^"]+"', "", response.text, count=1)
    locations = ET.fromstring(clean_xml).findall(".//GpsLocationClass")

    if not locations:
        return {"observations_extracted": 0}

    observations = []
    for loc in locations:
        if _get_text(loc, "GpsLocked", "false").lower() != "true":
            continue
        observations.append({
            "source": _get_text(loc, "VehicleCode"),
            "type": "tracking-device",
            "subject_type": "vehicle",
            "recorded_at": _get_text(loc, "LocTime") + "Z",
            "location": {
                "lat": float(_get_text(loc, "Latitude", 0)),
                "lon": float(_get_text(loc, "Longitude", 0)),
            },
            "additional": {
                "speed_kmh": float(_get_text(loc, "Speed", 0)),
                "ignition": _get_text(loc, "Ignition", "false").lower() == "true",
                "netstar_id": _get_text(loc, "VehicleId"),
                "direction": float(_get_text(loc, "Direction", 0)),
                "driver_code": _get_text(loc, "DriverCode"),
                "location_description": _get_text(loc, "Location"),
                "zone": _get_text(loc, "Zone"),
                "odo_km": float(_get_text(loc, "Odo", 0)) if _get_text(loc, "Odo") is not None else None,
                "operating_time_seconds": int(_get_text(loc, "OperatingTime", 0)) if _get_text(loc, "OperatingTime") is not None else None,
            },
        })

    await send_observations_to_gundi(observations=observations, integration_id=integration.id)
    return {"observations_extracted": len(observations)}
