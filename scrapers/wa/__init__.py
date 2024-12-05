from openstates.scrape import State
from .events import WAEventScraper
from .bills import WABillScraper

settings = dict(SCRAPELIB_TIMEOUT=300)


class Washington(State):
    scrapers = {
        "events": WAEventScraper,
        "bills": WABillScraper,
    }
    historical_legislative_sessions = [
        {
            "_scraped_name": "2009",
            "identifier": "2009",
            "name": "2009-2010 Regular Session",
            "start_date": "2009-01-12",
            "end_date": "2010-03-11",
        },
        {
            "_scraped_name": "2011",
            "identifier": "2011",
            "name": "2011-2012 Regular Session",
            "start_date": "2011-01-10",
            "end_date": "2012-03-08",
        },
        {
            "_scraped_name": "2013",
            "identifier": "2013",
            "name": "2013-2014 Regular Session",
            "start_date": "2013-01-14",
            "end_date": "2014-03-14",
        },
        {
            "_scraped_name": "2015",
            "identifier": "2015",
            "name": "2015-2016 Regular Session",
            "start_date": "2015-01-12",
            "end_date": "2016-03-10",
        },
        {
            "_scraped_name": "2017",
            "identifier": "2017",
            "name": "2017-2018 Regular Session",
            "start_date": "2017-01-09",
            "end_date": "2018-03-08",
        },
        {
            "_scraped_name": "2019",
            "identifier": "2019",
            "name": "2019-2020 Regular Session",
            "start_date": "2019-01-14",
            "end_date": "2020-03-12",
        },
        {
            "_scraped_name": "2021",
            "classification": "primary",
            "identifier": "2021",
            "name": "2021-2022 Regular Session",
            "start_date": "2021-01-11",
            "end_date": "2022-03-10",
            "active": False,
        },
        {
            "_scraped_name": "2023",
            "classification": "primary",
            "identifier": "2023-24",
            "name": "2023-2024 Regular Session",
            "start_date": "2023-01-09",
            "end_date": "2024-03-07",
            "active": False,
        },
        {
            "_scraped_name": "2025-26",
            "classification": "primary",
            "identifier": "2025-2026",
            "name": "2025-2026 Regular Session",
            "start_date": "2025-01-13",
            "end_date": "2026-03-06",
            "active": True,
        },
        {
            "_scraped_name": "2025",
            "classification": "primary",
            "identifier": "2025",
            "name": "2025-2026 Regular Session",
            "start_date": "2024-12-02",
            "end_date": "2026-12-31",
            "active": False,
        },
    ]
    ignored_scraped_sessions = [
        "2007",
        "2005",
        "2003",
        "2001",
        "1999",
        "1997",
        "1995",
        "1993",
        "1991",
        "1989",
        "1987",
        "1985",
    ]

    def get_session_list(self):
        from utils.lxmlize import url_xpath

        return url_xpath(
            "https://apps.leg.wa.gov/billinfo/",
            '//select[@id="biennium"]/option/text()',
            verify=False,
        )
