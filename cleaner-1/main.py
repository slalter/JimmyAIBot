#when called, this function looks through existing conversation jsons and:
#1 identifies ones that need followup, and initates that followup. 
#2 identifies conversations that are closed, and moves them into the "closed" folder in the bin.

#NECESSARY TODO:
#build functionality for knowing when messages were sent
    #this is best achieved by... 
    #messages now have a timestamp attribute, returned in their json as appropriate.
import functions_framework
from google.cloud import storage
import json
import os

@functions_framework.http
def hello_get(request):
    storage_client = storage.Client()
    bucket_name = "leadsgptancelet"
    for blob in storage_client.bucket(bucket_name).list_blobs:
        print(blob.updated)
    return 200