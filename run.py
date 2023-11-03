#!/usr/bin/env python3
import os
import datetime
import math

import requests
import pydantic
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from flask import Flask, request,jsonify

load_dotenv()


class Departure(pydantic.BaseModel):
    line: str
    destination: str
    timetabled: datetime.datetime
    estimated: datetime.datetime | None


class Response(pydantic.BaseModel):
    departures: list[Departure] = pydantic.Field(default_factory=list)

def get_departures(requested_lines: list[str]) -> list[Departure]:
    url = "https://api.opentransportdata.swiss/trias2020"

    request = """
    <?xml version="1.0" encoding="UTF-8"?>
    <Trias version="1.1" xmlns="http://www.vdv.de/trias" xmlns:siri="http://www.siri.org.uk/siri" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <ServiceRequest>
            <siri:RequestTimestamp>2023-11-03T08:38:09.013Z</siri:RequestTimestamp>
            <siri:RequestorRef>API-Explorer</siri:RequestorRef>
            <RequestPayload>
                <StopEventRequest>
                    <Location>
                        <LocationRef>
                            <StopPointRef>8592922</StopPointRef>
                        </LocationRef>
                        <DepArrTime>{time:%Y-%m-%dT%H:%M:%S}</DepArrTime>
                    </Location>
                    <Params>
                        <NumberOfResults>40</NumberOfResults>
                        <StopEventType>departure</StopEventType>
                        <IncludePreviousCalls>false</IncludePreviousCalls>
                        <IncludeOnwardCalls>false</IncludeOnwardCalls>
                        <IncludeRealtimeData>true</IncludeRealtimeData>
                    </Params>
                </StopEventRequest>
            </RequestPayload>
        </ServiceRequest>
    </Trias>
    """.strip()

    request = request.format(time=datetime.datetime.now())
    token = os.environ.get("API_KEY")
    #  token = "57c5dbbbf1fe4d000100001842c323fa9ff44fbba0b9b925f0c052d1"
    r = requests.request(
        method="post",
        url=url,
        data=request,
        headers={"Content-Type": "text/xml", "Authorization": token},
    )

    #  print(r.encoding)
    #  print(r.apparent_encoding)
    r.encoding = r.apparent_encoding

    namespaces = {
        "siri": "http://www.siri.org.uk/siri",
        "trias": "http://www.vdv.de/trias",
        "acsb": "http://www.ifopt.org.uk/acsb",
        "ifopt": "http://www.ifopt.org.uk/ifopt",
        "datex2": "http://datex2.eu/schema/1_0/1_0",
    }

    tree = ET.fromstring(r.text)

    requested_lines = {"18"}


    departures = []

    for stop_event in tree.findall(".//trias:StopEvent", namespaces=namespaces):
        this_call = stop_event.find("trias:ThisCall", namespaces=namespaces)
        assert this_call is not None
        service = stop_event.find("trias:Service", namespaces=namespaces)
        assert service is not None
        #  print(this_call, service)

        published_line_name = service.find(
            "trias:PublishedLineName/trias:Text", namespaces=namespaces
        )
        assert published_line_name is not None
        published_line_name = published_line_name.text
        assert published_line_name is not None
        if published_line_name not in requested_lines:
            continue

        destination_text = service.find(
            "trias:DestinationText/trias:Text", namespaces=namespaces
        )
        assert destination_text is not None
        destination_text = destination_text.text
        assert destination_text is not None

        if "CERN" not in destination_text:
            continue
        #  print(published_line_name, "->", destination_text)

        service_departure_timetabled = this_call.find(
            "trias:CallAtStop/trias:ServiceDeparture/trias:TimetabledTime",
            namespaces=namespaces,
        )
        assert service_departure_timetabled is not None, "Node not found"
        service_departure_timetabled = service_departure_timetabled.text
        assert service_departure_timetabled is not None, "Text not found"

        service_departure_estimated = this_call.find(
            "trias:CallAtStop/trias:ServiceDeparture/trias:EstimatedTime",
            namespaces=namespaces,
        )

        service_departure_estimated = (
            service_departure_estimated.text
            if service_departure_estimated is not None
            else None
        )

        timetabled = datetime.datetime.strptime(
            service_departure_timetabled, "%Y-%m-%dT%H:%M:%SZ"
        )
        timetabled.replace(tzinfo=datetime.timezone.utc)

        estimated = None
        if service_departure_estimated is not None:
            estimated = datetime.datetime.strptime(
                service_departure_estimated, "%Y-%m-%dT%H:%M:%SZ"
            )
            estimated.replace(tzinfo=datetime.timezone.utc)
        #  print("  ", timetabled, "/", estimated)

        departures.append(
            Departure(
                line=published_line_name,
                destination=destination_text,
                timetabled=timetabled,
                estimated=estimated,
            )
        )

    return departures


app = Flask(__name__)

@app.get("/")
def load_departures():
    departures = get_departures(["18"])
    return Response(departures=departures).json(), 200, {"Content-Type": "application/json"}

@app.get("/as-text")
def departures_as_text():
    departures = get_departures(["18"])

    num = int(request.args.get("num", 2))

    text = ""
    if min(num, len(departures)) == 1:
        text = "Die nächste Tram zum CERN kommt in"
    else:
        text = "Die nächsten Trams zum CERN kommen in"

    frags = []

    for  dep in departures[:num]:
        best_time = dep.estimated or dep.timetabled
        delta = best_time - datetime.datetime.utcnow()
        minutes = math.floor(delta.total_seconds()/60)
        if minutes == 1:
            frags.append("einer Minute")
        else:
            frags.append(f"{minutes} Minuten")


    times = ", ".join(frags[:-1]) + " und " + frags[-1]
    text +=  " " + times

    return jsonify({"text": text})


