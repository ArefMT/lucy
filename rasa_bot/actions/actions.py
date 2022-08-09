from typing import Dict, Text, Any, List

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import ValidationAction
from rasa_sdk import Action
from rasa_sdk.events import  SlotSet
import requests
from  rasa_sdk.events  import Restarted

url_db = 'http://441:8082/api'
url_tts = 'http://4:8081/repeat'

class ExtractCustomSlotMappings(ValidationAction):
    async def extract_user_job_title(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:

        intent_of_last_user_message = tracker.get_intent_of_latest_message()
        current_value =  tracker.get_slot("user_job_title")
        if current_value is None:
            if intent_of_last_user_message == 'answer_name_role':
                current_value = next(tracker.get_latest_entity_values('role'), 'Not found')
                id = tracker.sender_id
                msg = tracker.latest_message["text"]
                load = {'user_id': id, 'user_job_title': current_value, 'user_job_title_mgs':msg}
                r = requests.post(url_db, json=load)

        return {"user_job_title": current_value}

    async def extract_user_years_of_experience( self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
        intent_of_last_user_message = tracker.get_intent_of_latest_message()
        current_value =  tracker.get_slot("user_years_of_experience")
        if current_value is None:
            if intent_of_last_user_message == 'answer_give_years_of_experience':
                current_value = next(tracker.get_latest_entity_values('DATE'), 'Not found')
                entities = tracker.latest_message["entities"]
                for i in entities:
                    if i['entity'] == 'DATE' and i['extractor'] == 'SpacyEntityExtractor':
                        current_value = i['value']
                        break
                id = tracker.sender_id
                msg = tracker.latest_message["text"]
                load = {'user_id': id, 'user_years_of_experience': current_value, 'user_years_of_experience_msg': msg}
                r = requests.post(url_db, json=load)

        return {"user_years_of_experience": current_value}


    async def extract_user_stories(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[
        Text, Any]:
        intent_of_last_user_message = tracker.get_intent_of_latest_message()
        current_value =  tracker.get_slot("user_stories")

        if current_value is None and intent_of_last_user_message == 'answer_userstory':
            user = tracker.get_latest_entity_values("user")
            if user is None:
                user = "Not found"
            else:
                user = ' '.join(user)

            functionality = next(tracker.get_latest_entity_values("functionality"), 'Not found')
            benefit = next(tracker.get_latest_entity_values("benefit"), "Not found")

            current_value = {'first_user': user, 'first_func': functionality,'first_benf': benefit,}

            id = tracker.sender_id
            msg = tracker.latest_message["text"]
            load = {'user_id': id, 'first_suser_stories': current_value, 'first_user_stories_msg': msg}
            r = requests.post(url_db, json=load)

        elif current_value is not None and intent_of_last_user_message == 'answer_userstory':
            userstories_dict = tracker.get_slot("user_stories")
            user = tracker.get_latest_entity_values("user")
            if user is None:
                user = "Not found"
            else:
                user = ' '.join(user)
            functionality = next(tracker.get_latest_entity_values("functionality"), 'Not found')
            benefit = next(tracker.get_latest_entity_values("benefit"), "Not found")
            second_dict = {'second_user': user,'second_func': functionality, 'second_benf': benefit}
            current_value = {**second_dict,**userstories_dict}

            id = tracker.sender_id
            msg = tracker.latest_message["text"]
            load = {'user_id': id, 'second_suser_stories': second_dict, 'second_user_stories_msg': msg}
            r = requests.post(url_db, json=load)

        return {"user_stories": current_value}

    async def extract_features_importance( self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
        intent_of_last_user_message = tracker.get_intent_of_latest_message()
        current_value = tracker.get_slot("features_importance")
        if current_value is None:
            if intent_of_last_user_message == 'give_feature_importance':
                id = tracker.sender_id
                msg = tracker.latest_message["text"]
                current_value = {'first_feature_importance': msg}
                load = {'user_id': id, 'features_importance': current_value,}
                r = requests.post(url_db, json=load)
        elif current_value and intent_of_last_user_message == 'give_feature_importance':
            id = tracker.sender_id
            msg = tracker.latest_message["text"]
            second_feature_importance = {'second_feature_importance':msg}
            current_value = {**second_feature_importance,**current_value}
            load = {'user_id': id, 'features_importance': current_value}
            r = requests.post(url_db, json=load)

        return {"features_importance": current_value}



# #Spacy
#     async def extract_project_deadline( self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
#         intent_of_last_user_message = tracker.get_intent_of_latest_message()
#         current_value =  tracker.get_slot("project_deadline")
#         if current_value is None:
#             if intent_of_last_user_message == 'answer_give_deadline':
#                 current_value = next(tracker.get_latest_entity_values('DATE'), 'Not found')
#                 entities = tracker.latest_message["entities"]
#                 for i in entities:
#                     if i['entity'] == 'DATE' and i['extractor'] == 'SpacyEntityExtractor':
#                         current_value = i['value']
#                         break
#                 id = tracker.sender_id
#                 msg = tracker.latest_message["text"]
#                 load = {'user_id': id, 'project_deadline': current_value, 'project_deadline_mgs': msg}
#                 r = requests.post(url_db, json=load)
#
#         return {"project_deadline": current_value}
# #Spacy
#     async def extract_project_budget( self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
#         intent_of_last_user_message = tracker.get_intent_of_latest_message()
#         current_value =  tracker.get_slot("project_budget")
#         if current_value is None:
#             if intent_of_last_user_message == 'answer_give_budget':
#                 current_value = next(tracker.get_latest_entity_values('MONEY'), 'Not found')
#                 entities = tracker.latest_message["entities"]
#                 for i in entities:
#                     if i['entity'] == 'MONEY' and i['extractor'] == 'SpacyEntityExtractor':
#                         current_value = i['value']
#                         break
#                 id = tracker.sender_id
#                 msg = tracker.latest_message["text"]
#                 load = {'user_id': id, 'project_budget': current_value, 'project_budget_msg': msg}
#                 r = requests.post(url_db, json=load)
#
#         return {"project_budget": current_value}

##################################################################################


class ActionAskYearsOfExperience(Action):

    def name(self) -> Text:
        return "action_ask_years_of_experience"

    async def run(
        self, dispatcher, tracker: Tracker, domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        role = tracker.get_slot('user_job_title')
        if role != 'Not found':
            dispatcher.utter_message(text = f"And how long have you been working as {role}?")
        else:
            dispatcher.utter_message(text="And how long have you been working in this role?")
        return []


class ActionRepeatLastUtterance(Action):

    def name(self) -> Text:
        return "action_repeat_last_utterance"

    async def run(
        self, dispatcher, tracker: Tracker, domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        id = tracker.sender_id
        load = {'recipient_id': id,}
        r = requests.post(url_tts, json=load)

        return []


class ActionRestart(Action):

  def name(self) -> Text:
      return "action_restart"

  async def run(
      self, dispatcher, tracker: Tracker, domain: Dict[Text, Any]
  ) -> List[Dict[Text, Any]]:

      # custom behavior

      return [Restarted()]

# class ActionSetFirstInterviewSlot(Action):
#
#     def name(self) -> Text:
#         return "action_extract_is_first_interview"
#
#     async def run(
#         self, dispatcher, tracker: Tracker, domain: Dict[Text, Any],
#     ) -> List[Dict[Text, Any]]:
#
#         intent_of_last_user_message = tracker.get_intent_of_latest_message()
#         if intent_of_last_user_message == 'answer_deny_first_time_interview' or intent_of_last_user_message == 'deny':
#             current_value = False
#             id = tracker.sender_id
#             msg = tracker.latest_message["text"]
#             load = {'user_id': id, 'is_first_interview': current_value, 'user_is_first_interview': msg}
#             r = requests.post(url_db, json=load)
#
#         elif intent_of_last_user_message == 'affirm':
#             current_value = True
#             id = tracker.sender_id
#             msg = tracker.latest_message["text"]
#             load = {'user_id': id, 'is_first_interview': current_value, 'user_is_first_interview': msg}
#             r = requests.post(url_db, json=load)
#
#         return []
