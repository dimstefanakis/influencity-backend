from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson.natural_language_understanding_v1 import Features, ClassificationsOptions, CategoriesOptions, KeywordsOptions
import os

api_key = os.environ.get('WATSON_KEY')
url = os.environ.get('WATSON_URL')
model_id = os.environ.get('WATSON_MODEL_ID')

def extract_tags_from_question(question):
    auth = IAMAuthenticator(api_key)
    nlu = NaturalLanguageUnderstandingV1(version='2021-03-25', authenticator=auth)
    nlu.set_service_url(url)

    # print("Successfully connected with the NLU service")
    analysis = nlu.analyze(text=question, features=Features(classifications=ClassificationsOptions(model=model_id))).get_result()
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
            'is_weak': weak_results
        }
    except Exception as e:
        print(e)
        return {
            'tags': [],
            'umbrella_term': '',
            'is_weak': weak_results
        }