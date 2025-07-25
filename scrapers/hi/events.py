import datetime as dt
from openstates.scrape import Scraper, Event
from openstates.exceptions import EmptyScrape
from .utils import get_short_codes, make_data_url
from requests import HTTPError
import pytz
import lxml

URL = "https://www.capitol.hawaii.gov/session/upcominghearings.aspx"

TIMEZONE = pytz.timezone("Pacific/Honolulu")


class HIEventScraper(Scraper):
    seen_hearings = []
    chambers = {"lower": "House", "upper": "Senate", "joint": "Joint"}

    def get_related_bills(self, href):
        ret = []
        try:
            self.info(f"GET {make_data_url(href)}")
            page = lxml.html.fromstring(
                self.get(make_data_url(href), verify=False).content
            )
        except HTTPError:
            return ret

        bills = page.xpath(".//a[contains(@href, 'Bills')]")
        for bill in bills:
            try:
                row = next(bill.iterancestors(tag="tr"))
            except StopIteration:
                continue
            tds = row.xpath("./td")
            descr = tds[1].text_content()
            for i in ["\r\n", "\xa0"]:
                descr = descr.replace(i, "")
            ret.append(
                {
                    "bill_id": bill.text_content(),
                    "type": "consideration",
                    "descr": descr,
                }
            )

        return ret

    def scrape(self):

        get_short_codes(self)
        self.info(f"GET {make_data_url(URL)}")
        page = self.get(make_data_url(URL), verify=False).content
        page = lxml.html.fromstring(page)

        if page.xpath("//td[contains(string(.),'No Hearings')]"):
            raise EmptyScrape

        table = page.xpath("//table[contains(@id, 'MainContent_GridView1')]")[0]

        events = set()
        for event in table.xpath(".//tr")[1:]:
            tds = event.xpath("./td")
            committee = tds[0].text_content().strip()

            # Multi-committee events will be CODE1/CODE2/CODE3
            if "/" in committee:
                coms = committee.split("/")
                com_names = []
                for com in coms:
                    com_names.append(
                        f"{self.chambers[self.short_ids[com]['chamber']]} {self.short_ids[com]['name']}"
                    )
                descr = ", ".join(com_names)
            elif self.short_ids.get(committee):
                descr = f"{self.chambers[self.short_ids[committee]['chamber']]} {self.short_ids[committee]['name']}"
            else:
                descr = [x.text_content() for x in tds[1].xpath(".//span")]
                if len(descr) != 1:
                    raise Exception
                descr = descr[0].replace(".", "").strip()

            when = tds[2].text_content().strip()
            where = tds[3].text_content().strip()
            notice = tds[4].xpath(".//a")[0]
            notice_href = notice.attrib["href"]
            notice_name = notice.text

            """
            the listing page shows the same hearing in multiple rows.
            combine these -- get_related_bills() will take care of adding the bills
            and descriptions
            Otherwise, skip this line
            """
            if notice_href in self.seen_hearings:
                continue
            else:
                self.seen_hearings.append(notice_href)

            when = dt.datetime.strptime(when, "%m/%d/%Y %I:%M %p")
            when = TIMEZONE.localize(when)
            event_name = f"{descr}#{where}#{when}"
            if event_name in events:
                self.warning(f"Duplicate event {event}")
                continue
            events.add(event_name)
            event = Event(
                name=descr,
                start_date=when,
                classification="committee-meeting",
                description=descr,
                location_name=where,
            )
            event.dedupe_key = event_name
            if "/" in committee:
                committees = committee.split("/")
            else:
                committees = [committee]

            for committee in committees:
                if "INFO" not in committee and committee in self.short_ids:
                    committee = f"{self.chambers[self.short_ids[committee]['chamber']]} {self.short_ids[committee]['name']}"
                event.add_committee(committee, note="host")

            event.add_source(URL)
            event.add_document(notice_name, notice_href, media_type="text/html")
            for bill in self.get_related_bills(notice_href):
                a = event.add_agenda_item(description=bill["descr"].strip())
                bill["bill_id"] = bill["bill_id"].split(",")[0]
                a.add_bill(bill["bill_id"], note=bill["type"])

            if tds[5].xpath(".//a"):
                video_url = tds[5].xpath(".//a/@href")[0]
                self.info(video_url)
                event.add_media_link("Hearing Stream", video_url, "text/html")

            yield event
