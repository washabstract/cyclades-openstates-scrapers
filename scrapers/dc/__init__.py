import os
import requests
from openstates.scrape import State
from .bills import DCBillScraper
from .events import DCEventScraper
from utils.secrets import get_secret


class DistrictOfColumbia(State):
    scrapers = {
        "events": DCEventScraper,
        "bills": DCBillScraper,
    }
    historical_legislative_sessions = [
        {
            "_scraped_name": "19",
            "identifier": "19",
            "name": "19th Council Period (2011-2012)",
            "start_date": "2011-01-01",
            "end_date": "2012-12-31",
        },
        {
            "_scraped_name": "20",
            "identifier": "20",
            "name": "20th Council Period (2013-2014)",
            "start_date": "2013-01-01",
            "end_date": "2014-12-31",
        },
        {
            "_scraped_name": "21",
            "identifier": "21",
            "name": "21st Council Period (2015-2016)",
            "start_date": "2015-01-01",
            "end_date": "2016-12-31",
        },
        {
            "_scraped_name": "22",
            "identifier": "22",
            "name": "22nd Council Period (2017-2018)",
            "start_date": "2017-01-02",
            "end_date": "2018-12-31",
        },
        {
            "_scraped_name": "23",
            "identifier": "23",
            "name": "23rd Council Period (2019-2020)",
            "start_date": "2019-01-02",
            "end_date": "2020-12-31",
        },
        {
            "_scraped_name": "24",
            "identifier": "24",
            "name": "24th Council Period (2021-2022)",
            "start_date": "2021-01-02",
            "end_date": "2022-12-31",
            "active": False,
        },
        {
            "_scraped_name": "25",
            "identifier": "25",
            "name": "25th Council Period (2023-2024)",
            "start_date": "2023-01-02",
            "end_date": "2024-12-31",
            "active": False,
        },
        {
            "_scraped_name": "26",
            "identifier": "26",
            "name": "26th Council Period (2025-2026)",
            "start_date": "2025-01-02",
            "end_date": "2025-12-31",
            "active": True,
        },
    ]
    ignored_scraped_sessions = [
        "18",
        "17",
        "16",
        "15",
        "14",
        "13",
        "12",
        "11",
        "10",
        "9",
        "8",
    ]

    def get_session_list(self):
        apikey = get_secret("DC_API_KEY")
        useragent = os.getenv("USER_AGENT", "openstates")
        headers = {
            "Authorization": apikey,
            "Accept": "application/json",
            "User-Agent": useragent,
        }
        resp = requests.get(
            "https://lims.dccouncil.gov/api/v2/PublicData/CouncilPeriods",
            headers=headers,
            verify=False,
        )
        resp.raise_for_status()
        sessions = []
        for session in resp.json():
            sessions.append(str(session["councilPeriodId"]))
        return sessions
