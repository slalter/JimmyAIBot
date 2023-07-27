#when called, this function looks through existing conversation jsons and identifies ones that need followup, and initates that followup. 
import functions_framework
from google.cloud import storage
from flask import make_response
import json
import os
import requests
from datetime import datetime, timezone
import pytz

@functions_framework.http
def hello_get(request):
    storage_client = storage.Client()
    bucket_name = os.environ.get("bucket_name")
    bucket = storage_client.get_bucket(bucket_name)

    #load .txt of closed conversations, separated by spaces.
    blob = bucket.blob("closed.txt")
    with blob.open("r") as f:
        closed = f.read()
    

    for blob in bucket.list_blobs(prefix='leads'):
        try:
            name = str(blob.name)[6:16]
            print(name)
        except Exception as e:
            print("unable to get blob name due to" + str(e))
            try:
                requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/errortext", json = {"Body": "Unable to get blob name!!"})
            except:
                print("DAMN SON WE SOL cleaner line 31")
            continue
        
        #see if conversation is closed
        if name in closed:
            print("closed. not poking.")
            continue

        #see how old we are. Poke old, unclosed blobs. Poked blobs self-close when we post to FullBot.
        try:
            if((pytz.utc.localize(datetime.now())-blob.updated).total_seconds()>=5*60):
                print("attempting to poke blob.")
                jsonOut = {"Body":"poke","From":"+1" + name}
                response = requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/FullBot",json=json.dumps(jsonOut))
                print(response)
        except Exception as e:
            print("unable to poke" + str(blob.name) + "due to " + str(e))
        
        

    
    return make_response("success",200)