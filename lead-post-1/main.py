import functions_framework
import json
import requests
from flask import make_response, jsonify
from google.cloud import storage

@functions_framework.http
def hello_http(request):
    print(request.get_json())
    response = rprocess(request.get_json())
    if(response.status_code==200):
      try: 
          name = request.get_json()["body"]["first_name"]
      except:
          print("unable to get name.")
          name = "unknown"
      initjson = {'Body': 'start', 'From' : "+1" + str(request.get_json()["body"]["number"]), "Name":name}
      try:
        storage_client = storage.Client()
        bucket_name = "leadbackups"
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(request.get_json()["body"]["number"]+"backup.json")
        with blob.open("w") as f:
            f.write(json.dumps(request.get_json()))
      except:
        try:
            err = requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/errortext", json = {"Body": "Unable to write backup lead for " + request.get_json()["body"]["number"]})
        except:
            pass

      try:
        resp2 = requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/FullBot", json=json.dumps(initjson))
      except Exception as e:
        print("UNABLE TO INITIATE PURCHASED LEAD")
        try:
          err = requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/errortext", json = {"Body": "Unable to initiate purchased lead for " + request.get_json()["body"]["number"]})
        except:
            pass
    return response

#accept or reject.
def rprocess(request):
    reason = ""
    print("json loaded")
    #if(compare to existing leads):
    try:
        if(request["body"]["parent_id"]):
            pass
        else:
            reason = "missing parent_id field"
        if(request["body"]["sub_id"]):
            pass
        else:
            reason = reason + "missing sub_id field"
        try:
            storage_client = storage.Client()
            bucket_name = "leadsgptancelet"
            leads = storage_client.list_blobs(bucket_name)
            for lead in leads:
                if str(request["body"]["number"]) in str(lead):
                    reason = "duplicate"
                    break
        except Exception as e:
            print("failed to check for duplicates due to " + str(e))
            reason = "server error in duplicate check. dev notified."
            try:
                err = requests.post("https://us-central1-opportune-box-390021.cloudfunctions.net/errortext", json = {"Body": "Unable to check for duplicates for " + request.get_json()["body"]["number"]})
            except:
                pass
            return make_response(jsonify({"accepted":0, "parent_id":request["body"]["parent_id"],"sub_id":request["body"]["sub_id"],"reason":reason}),409,{})
            
        if ((int(request["body"]["age"])>63) or (int(request["body"]["age"])<19)):
            reason = "bad field: age must be between 19 and 63."
        if request["body"]["MM_enroll"]==1 or request["body"]["MM_enroll"]=="1":
            reason = "bad field: MM_enroll must be 0 (not enrolled in medicare or medicade)"
        
        income = request["body"]["yearly_income"]
        try:
            int(income)
            income = int(income)
            if int(request["body"]["yearly_income"])>35000 or int(request["body"]["yearly_income"])<13000:
                reason = "bad field: yearly_income must be between 13000 and 35000"
        except:
            print("income was not an integer. Attempting to determine category.")
            if(income!="25K - 35K"):#############needs mod
                print("income was " + str(income) + " and was rejected.")
                reason = "bad field: yearly_income must be between 13k and 35k or invalid category"
    except Exception as e:
        print("failed to check due to " + str(e))
        return make_response("bad request. Refer to documentation or contact dev.",400)
    
    if reason == "":
        return make_response(jsonify({"accepted":1, "parent_id":request["body"]["parent_id"], "sub_id":request["body"]["sub_id"]}),200,{})
    else:
        return make_response(jsonify({"accepted":0, "parent_id":request["body"]["parent_id"],"sub_id":request["body"]["sub_id"],"reason":reason}),409,{})