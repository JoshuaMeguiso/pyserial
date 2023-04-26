import sys
import time
import json
import httpx
import serial
import asyncio
import requests
import RPi.GPIO as GPIO
from pydantic import BaseModel
from typing import List, Optional
from mfrc522 import SimpleMFRC522
from fastapi import FastAPI, HTTPException
from datetime import datetime, time, timedelta
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
reader = SimpleMFRC522()

# Allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ser = serial.Serial('/dev/ttyAMA0', 9600) # Adjust the serial port as needed

class Credits(BaseModel):
    value: int

class StringBody(BaseModel):
    command_string: str

    class Config:
        json_loads = json.loads

@app.get("/credits")
async def get_credits():
    received_string = ""
    if ser.in_waiting > 0:
        incoming_char = ser.read().decode('utf-8')
        print(incoming_char)
        if hex(ord(incoming_char)) != "0xd":
            if incoming_char == '1':
                return Credits(value=20)
            elif incoming_char == '2':
                return Credits(value=50)
            elif incoming_char == '3':
                return Credits(value=100)
            elif incoming_char == '4':
                return Credits(value=200)
            elif incoming_char == '5':
                return Credits(value=500)
            elif incoming_char == '6':
                return Credits(value=1000)
            else:
                return Credits(value=0)
    else:
        return Credits(value=0)

@app.get("/uid")
async def get_uid():
    try:
        uid, text = reader.read()
        rfid_read = str(uid)
        #piUID = ["123", "321", "456", "654"]
        #nodeUID = ["abc", "cba", "def", "fed"]
        #index = 0
        #while index < len(piUID):
        #    if rfid_read == piUID[index]: 
        #        print({"rfid :" + nodeUID[index])
        #        return nodeUID[index]
        #    index += 1
        return rfid_read
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send_string")
async def send_string(string_body: StringBody):
    try:
        char_array = list(string_body.command_string)
        for char in char_array:
            ser.write(char.encode())
            time.sleep(0.005)
            print("Sent: " + char)
        return {"message": "Characters sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


json_list: Optional[List] = None

async def fetch_data(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            json_response = response.json()
            return json_response.get("data")

async def schedule_task():
    global json_list

    # Send the GET request immediately on startup
    url = "https://endorm-server.onrender.com/user/room"
    json_list = await fetch_data(url)
    if json_list:
        print("Received JSON list on startup:", json_list)
    else:
        print("No data received on startup")

    # Then start the loop for scheduling the task every midnight
    while True:
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), time())
        seconds_until_midnight = (midnight - now).seconds

        # Sleep until midnight
        await asyncio.sleep(seconds_until_midnight)

        # Send the GET request and anticipate a JSON list
        json_list = await fetch_data(url)
        if json_list:
            print("Received JSON list:", json_list)
        else:
            print("No data received")

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(schedule_task())

@app.get("/json_list")
async def get_json_list():
    return {"json_list": json_list}

@app.post("/door/{roomID}/{rfid}")
async def door(roomID: str, rfid: str):
    # Send the same request to another endpoint
    url = f"https://endorm-server.onrender.com/user/door/{roomID}"
    data = {"rfid": rfid}
    response = requests.post(url, json=data)
    return response.json()