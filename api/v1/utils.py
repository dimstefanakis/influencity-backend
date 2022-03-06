from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson.natural_language_understanding_v1 import Features, ClassificationsOptions, CategoriesOptions, KeywordsOptions
import datetime
import requests
import json
import os

api_key = os.environ.get('WATSON_KEY')
url = os.environ.get('WATSON_URL')
model_id = os.environ.get('WATSON_MODEL_ID')


def extract_tags_from_question(question):
    auth = IAMAuthenticator(api_key)
    nlu = NaturalLanguageUnderstandingV1(
        version='2021-03-25', authenticator=auth)
    nlu.set_service_url(url)

    # print("Successfully connected with the NLU service")
    try:
        analysis = nlu.analyze(text=question, features=Features(
            classifications=ClassificationsOptions(model=model_id))).get_result()
    except Exception as e:
        return {
            'tags': [],
            'umbrella_term': '',
            'is_weak': False,
            'status': 'error'
        }
    weak_results = False
    try:
        # model is not really optimized so anything above 0.3 should be good for now
        if analysis['classifications'][0]['confidence'] < 0.3:
            weak_results = True
        tags = analysis['classifications'][0]['class_name'].split(',')
        # the umbrella term will always be the last item of the class_name list
        umbrella_term = tags[-1]
        return {
            'tags': tags[:-1],
            'umbrella_term': umbrella_term,
            'is_weak': weak_results,
            'status': 'success'
        }
    except Exception as e:
        print(e)
        return {
            'tags': [],
            'umbrella_term': '',
            'is_weak': weak_results,
            'status': 'error'
        }

# Europe/London is GMT timezone equal to UTC that server uses
def create_meeting(start_time, duration, coach):
    meetingdetails = {"topic": "Troosh QA session",
                      "type": 2,
                      "start_time": start_time.isoformat(),
                      "duration": duration,
                      "timezone": "Europe/London",
                      "agenda": f"Your debug session with {coach.name} is coming right up!",

                      "recurrence": {"type": 1,
                                     "repeat_interval": 1
                                     },
                      "settings": {"host_video": "true",
                                   "participant_video": "true",
                                   "join_before_host": "False",
                                   "mute_upon_entry": "False",
                                   "watermark": "true",
                                   "audio": "voip",
                                   "auto_recording": "cloud"
                                   }
                      }

    headers = {'authorization': 'Bearer ' + os.environ.get('ZOOM_JWT'),
               'content-type': 'application/json'}
    r = requests.post(
        f'https://api.zoom.us/v2/users/me/meetings',
        headers=headers, data=json.dumps(meetingdetails))

    print("\n creating zoom meeting ... \n")
    # print(r.text)
    # converting the output into json and extracting the details
    y = json.loads(r.text)
    join_URL = y["join_url"]
    meetingPassword = y["password"]
    start_time = datetime.datetime.strptime(
        y['start_time'], '%Y-%m-%dT%H:%M:%S%z')

    print(
        f'\n here is your zoom meeting link {join_URL} and your \
        password: "{meetingPassword}"\n')

    return {'url': join_URL, 'password': meetingPassword, 'start_time': start_time}
