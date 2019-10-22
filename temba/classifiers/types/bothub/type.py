from ...models import ClassifierType, Intent
from .views import ConnectView
from temba.request_logs.models import HTTPLog

import requests
from django.utils import timezone


class BotHubType(ClassifierType):
    """
    Type for classifiers from Bothub
    """

    CONFIG_ACCESS_TOKEN = "access_token"

    name = "BotHub"
    slug = "bh"
    icon = "icon-bothub"

    connect_view = ConnectView
    connect_blurb = """
        <a href="https://bothub.it">Bothub</a> is the open source and easy training NLP system developed by Ilhasoft and supported by UNICEF. It already supports 29 languages ​​and is evolving to include languages ​​and dialects of remote cultures. It´s ideal for bots of any size and complexity.
        """

    form_blurb = """
        You can your repository on Bothub here, with the name and with repository token.
        """

    INTENT_URL = "https://nlp.bothub.it/info/"

    @classmethod
    def get_active_intents_from_api(cls, classifier, logs):
        access_token = classifier.config[cls.CONFIG_ACCESS_TOKEN]

        start = timezone.now()
        response = requests.get(cls.INTENT_URL, headers={"Authorization": f"Bearer {access_token}"})
        elapsed = (timezone.now() - start).total_seconds() * 1000

        log = HTTPLog.from_response(HTTPLog.INTENTS_SYNCED, cls.INTENT_URL, response, classifier=classifier)
        log.request_time = elapsed
        logs.append(log)

        response.raise_for_status()
        response_json = response.json()

        intents = []
        for intent in response_json["intents"]:
            intents.append(Intent(name=intent, external_id=intent))

        return intents
