import csv
import re
import datetime
import pytz
import urllib.parse

from openstates.scrape import Scraper, Bill, VoteEvent
from openstates.exceptions import EmptyScrape

import lxml.html

from .common import get_slug_for_session, get_biennium_year

# from utils.secrets import get_secret

TIMEZONE = pytz.timezone("US/Central")
_AR_ORGANIZATION_ENTITY_NAME_KEYWORDS = [
    "Committee",
    "House Management",
    "Senate Efficiency",
]


class ARBillScraper(Scraper):
    ftp_user = ""
    ftp_pass = ""
    bills = {}
    sponsors_chamber_cache = {}

    def scrape(self, chamber=None, session=None):

        self.slug = get_slug_for_session(session)

        for i in self.jurisdiction.legislative_sessions:
            if i["identifier"] == session:
                self.session_name = i["name"]
                self.biennium = get_biennium_year(self.session_name)

        leg_chambers = [chamber] if chamber else ["upper", "lower"]

        for leg_chamber in leg_chambers:
            self.scrape_bill(leg_chamber, session)

        self.scrape_actions()

        if not self.bills:
            raise EmptyScrape

        for bill_id, bill in self.bills.items():
            yield bill

    def scrape_bill(self, chamber, session):
        url = "LegislativeMeasures.txt"

        page = csv.reader(self.get_utf_16_ftp_content(url).splitlines(), delimiter="|")

        for row in page:
            bill_chamber = {"H": "lower", "S": "upper"}[row[0]]

            if bill_chamber != chamber:
                continue
            bill_id = "%s%s %s" % (row[0], row[1], row[2])

            type_spec = re.match(r"(H|S)([A-Z]+)\s", bill_id).group(2)
            bill_type = {
                "B": "bill",
                "R": "resolution",
                "JR": "joint resolution",
                "CR": "concurrent resolution",
                "MR": "memorial",
                "CMR": "concurrent memorial",
            }[type_spec]

            if row[-1] != self.slug:
                self.warning(
                    f"Skipping row in session {row[-1]} because it does not match {self.slug}"
                )
                continue

            bill = Bill(
                bill_id,
                legislative_session=session,
                chamber=chamber,
                title=row[3],
                classification=bill_type,
            )
            bill.add_source(
                f"https://www.arkleg.state.ar.us/Bills/FTPDocument/?path=%2fSessionInformation%2{url}"
            )

            # need year before if it's a fiscal or special session beyond first
            year = session[0:4]
            if len(session) > 4 and session[-1] != "1":
                year = int(year) - 1
            bill_url = bill_id.replace(" ", "")

            # versions for special sessions have a different format
            is_special = True if len(session) > 5 else False
            if is_special:
                version_url = f"https://www.arkleg.state.ar.us/Bills/FTPDocument?path=%2FBills%2F{self.slug}%2FPublic%2F{bill_url}.pdf"
            else:
                version_url = f"https://www.arkleg.state.ar.us/assembly/{year}/{self.slug}/Bills/{bill_url}.pdf"
            bill.add_version_link(bill_id, version_url, media_type="application/pdf")

            # scrape_bill_page: this function is a generator so can't run this generator by simple call.
            for _ in self.scrape_bill_page(bill):
                pass

            self.bills[bill_id] = bill

    def scrape_actions(self):
        url = "ChamberActions.txt"
        page = csv.reader(self.get_utf_16_ftp_content(url).splitlines(), delimiter="|")

        for row in page:
            bill_id = "%s%s %s" % (row[1], row[2], row[3])

            if bill_id not in self.bills:
                continue

            if len(row) < 11:
                continue

            # different term
            if row[10] != self.slug:
                continue

            actor = {"H": "lower", "S": "upper"}[row[7].upper()]

            date = TIMEZONE.localize(
                datetime.datetime.strptime(row[5], "%Y-%m-%d %H:%M:%S.%f").replace(
                    microsecond=0
                )
            )

            action = row[6]

            action_type = []
            if action.startswith("Filed"):
                action_type.append("introduction")
            elif action.startswith("Read first time") or action.startswith(
                "Read the first time"
            ):
                action_type.append("reading-1")
            if re.match("Read the first time, .*, read the second time", action):
                action_type.append("reading-2")
            elif action.startswith("Read the third time and passed"):
                action_type.append("passage")
                action_type.append("reading-3")
            elif action.startswith("Read the third time"):
                action_type.append("reading-3")
            elif action.startswith("DELIVERED TO GOVERNOR"):
                action_type.append("executive-receipt")
            elif action.startswith("Notification"):
                action_type.append("executive-signature")
            elif "vetoed by the Governor" in action:
                action_type.append("executive-veto")
            elif "override" and "veto passed" in action.casefold():
                action_type.append("veto-override-passage")
                action_type.append("passage")
            elif "override" and "veto failed" in action.casefold():
                action_type.append("veto-override-failure")
                action_type.append("failure")

            if "referred to" in action:
                action_type.append("referral-committee")

            if "Returned by the Committee" in action:
                if "recommendation that it Do Pass" in action:
                    action_type.append("committee-passage-favorable")
                else:
                    action_type.append("committee-passage")

            if re.match(r"Amendment No\. \d+ read and adopted", action):
                action_type.append("amendment-introduction")
                action_type.append("amendment-passage")

            if not action:
                action = "[No text provided]"
            self.bills[bill_id].add_action(
                action, date, chamber=actor, classification=action_type
            )

    def get_entity_name(self, link):
        entity_type = "person"
        if any(keyword in link for keyword in _AR_ORGANIZATION_ENTITY_NAME_KEYWORDS):
            entity_type = "organization"
        return entity_type

    def get_chamber(self, name):
        chamber = ""
        if "senator" in name.lower() or "senate" in name.lower():
            chamber = "upper"
        elif "representative" in name.lower() or "house" in name.lower():
            chamber = "lower"
        elif "joint" in name.lower():
            chamber = "legislature"
        return chamber

    def scrape_bill_page(self, bill):
        # We need to scrape each bill page in order to grab associated votes.
        # It's still more efficient to get the rest of the data we're
        # interested in from the CSVs, though, because their site splits
        # other info (e.g. actions) across many pages
        session_year = int(self.slug[:4])
        odd_year = session_year if session_year % 2 else session_year - 1
        measureno = bill.identifier.replace(" ", "")
        url = (
            "https://www.arkleg.state.ar.us/assembly/%s/%s/"
            "Pages/BillInformation.aspx?measureno=%s" % (odd_year, self.slug, measureno)
        )
        page = self.get(url).text
        bill.add_source(url)
        page = lxml.html.fromstring(page)
        page.make_links_absolute(url)

        primary_sponsors_path = page.xpath(
            "//div[text()[contains(.,'Lead Sponsor:')]]/../div[2]/a"
        )
        for sponsor_path in primary_sponsors_path:
            primary_sponsors = sponsor_path.text_content().strip()
            if primary_sponsors == "":
                continue

            primary_sponsors_link = sponsor_path.attrib["href"]
            chamber = self.scrape_chamber(primary_sponsors_link)

            bill.add_sponsorship(
                primary_sponsors,
                classification="primary",
                entity_type=self.get_entity_name(primary_sponsors_link),
                primary=True,
                chamber=chamber,
            )

        other_primary_sponsors_path = page.xpath(
            "//div[text()[contains(.,'Other Primary Sponsor:')]]/../div[2]/a"
        )
        for sponsor_path in other_primary_sponsors_path:
            other_primary_sponsors = sponsor_path.text_content().strip()
            other_primary_sponsors_link = sponsor_path.attrib["href"]
            chamber = self.scrape_chamber(other_primary_sponsors_link)

            bill.add_sponsorship(
                other_primary_sponsors,
                classification="primary",
                entity_type=self.get_entity_name(other_primary_sponsors_link),
                primary=True,
                chamber=chamber,
            )

        cosponsor_path = page.xpath(
            "//div[text()[contains(.,'CoSponsors:')]]/../div[2]/a"
        )
        for sponsor_path in cosponsor_path:
            cosponsor = sponsor_path.text_content().strip()
            cosponsor_link = sponsor_path.attrib["href"]
            chamber = self.scrape_chamber(cosponsor_link)

            bill.add_sponsorship(
                cosponsor,
                classification="cosponsor",
                entity_type=self.get_entity_name(cosponsor_link),
                primary=False,
                chamber=chamber,
            )

        amendment_path = page.xpath(
            "//h3[text()[contains(.,'Amendments')]]/../../.."
            "/div/div/div[contains(@class, 'row tableRow')"
            " and descendant::div[contains(span, 'Amendment Number:')]]"
        )
        for row in amendment_path:
            div = list(row)
            amendment_number = (
                div[1].text_content().replace("Amendment Number:", "").strip()
            )
            for a in div[4]:
                amendment_url = a.attrib["href"].strip()
            amendment_date = div[3].text_content().strip()
            date = TIMEZONE.localize(
                datetime.datetime.strptime(amendment_date, "%m/%d/%Y %I:%M:%S %p")
            )
            date = "{:%Y-%m-%d}".format(date)
            bill.add_version_link(
                note="Amendment " + amendment_number,
                url=amendment_url,
                classification="amendment",
                date=date,
                media_type="application/pdf",
            )

        acts_link_xpath = (
            "//a[contains(@aria-label, 'Act') and contains(@href, '/Acts/')"
            " and contains(@aria-label,'.PDF')]"
        )

        if page.xpath(acts_link_xpath):
            act_link = page.xpath(acts_link_xpath)[0]
            act_link_parent = "//div[a[contains(@aria-label, 'Act') and contains(@href, '/Acts/') and contains(@aria-label,'.PDF')]]/text()"
            # two text matches here, before the image (blank), and after
            act_num = page.xpath(act_link_parent)[1].strip()
            act_num = f"Act {act_num}"
            act_url = act_link.xpath("@href")[0]
            bill.add_version_link(
                act_num,
                act_url,
                media_type="application/pdf",
                classification="became-law",
            )
            bill.add_citation(
                f"AR Acts, {self.biennium} - {self.session_name}",
                act_num,
                citation_type="chapter",
                url=act_url,
            )

        FI_path = page.xpath(
            "//h3[text()[contains(.,'DFA Fiscal Impacts')"
            " or contains(.,'BLR Fiscal Impacts')"
            " or contains(.,'Other Fiscal Impacts')]]"
            "/../../../div/div[contains(@class, 'row tableRow')]"
        )
        for row in FI_path:
            div = list(row)
            FI_number = div[0].text_content().replace("FI Number:", "").strip()
            for a in div[3]:
                if isinstance(a, lxml.html.HtmlComment):
                    continue
                FI_url = a.attrib["href"].strip()

            FI_date = div[2].text_content().replace("Date Issued:", "").strip()
            date = TIMEZONE.localize(datetime.datetime.strptime(FI_date, "%m/%d/%Y"))
            date = "{:%Y-%m-%d}".format(date)
            bill.add_document_link(
                note=FI_number,
                url=FI_url,
                classification="fiscal-note",
                date=date,
                media_type="application/pdf",
            )

        study_path = page.xpath(
            "//h3[text()[contains(.,'Actuarial Cost Studies')]]"
            "/../../../div/following::div[contains(@class, 'row tableRow')"
            " and descendant::div[contains(span, 'Study Number')]]"
        )
        for row in study_path:
            div = list(row)
            study_number = div[0].text_content().replace("Study Number:", "").strip()
            for a in div[2]:
                study_url = a.attrib["href"].strip()
            study_date = div[1].text_content().replace("Date Issued:", "").strip()
            date = TIMEZONE.localize(
                datetime.datetime.strptime(study_date, "%m/%d/%Y %I:%M:%S %p")
            )
            date = "{:%Y-%m-%d}".format(date)
            bill.add_document_link(
                note=study_number,
                url=study_url,
                classification="fiscal-note",
                date=date,
                media_type="application/pdf",
            )

        for link in page.xpath(
            "//*[@id='tableDataWrapper']/div/div[4]/a[contains(@href, '/Bills/Votes?id=')]"
        ):
            date = link.xpath("normalize-space(string(../../div[2]))")
            date = TIMEZONE.localize(
                datetime.datetime.strptime(date, "%m/%d/%Y %I:%M:%S %p")
            )

            motion = link.xpath("string(../../div[3])")
            yield from self.scrape_vote(bill, date, motion, link.attrib["href"])

    def scrape_vote(self, bill, date, motion, url):
        page = self.get(url).text
        if "not yet official" in page or "No data found for the vote" in page:
            # Sometimes they link to vote pages before they go live
            pass

        else:
            page = lxml.html.fromstring(page)

            if "Senate" in url:
                actor = "upper"
            else:
                actor = "lower"

            votevals = ["yes", "no", "not voting", "other"]
            yes_count = int(
                page.xpath(
                    "substring-after(//*[@id='bodyContent']/div/div/div/b[contains(text(), 'Yeas')], ': ')"
                )
            )
            no_count = int(
                page.xpath(
                    "substring-after(//*[@id='bodyContent']/div/div/div/b[contains(text(), 'Nays')], ': ')"
                )
            )
            not_voting_count = int(
                page.xpath(
                    "substring-after(//*[@id='bodyContent']/div/div/div/b[contains(text(), 'Non Voting')], ': ')"
                )
            )
            other_count = int(
                page.xpath(
                    "substring-after(//*[@id='bodyContent']/div/div/div/b[contains(text(), 'Present')], ': ')"
                )
            )
            passed = yes_count > no_count + not_voting_count + other_count
            vote_type = []
            vote_type.append("passage")
            if "override" and "veto" in motion.casefold():
                vote_type.append("veto-override")
            vote = VoteEvent(
                start_date=date,
                motion_text=motion,
                result="pass" if passed else "fail",
                classification=vote_type,
                chamber=actor,
                bill=bill,
            )
            try:
                excused_count = int(
                    page.xpath(
                        "substring-after(//*[@id='bodyContent']/div/div/div/b[contains(text(), 'Excused')], ': ')"
                    )
                )
                vote.set_count("excused", excused_count)
                votevals.append("excused")
            except (ValueError, IndexError):
                pass
            vote.set_count("yes", yes_count)
            vote.set_count("no", no_count)
            vote.set_count("not voting", not_voting_count)
            vote.set_count("other", other_count)
            vote.add_source(url)

            xpath = '//*[@id="bodyContent"]/div/div/div[(contains(@class, "voteList"))]'

            divs = page.xpath(xpath)

            for voteval, div in zip(votevals, divs):
                for a in div.xpath(".//a"):
                    name_path = a.attrib["href"].strip()
                    first_split = name_path.split("=")[1]
                    second_split = first_split.split("&")[0]
                    name = second_split.replace("+", " ")
                    if not name:
                        continue
                    else:
                        vote.vote(voteval, name)
            yield vote

    def scrape_chamber(self, url):
        if url in self.sponsors_chamber_cache:
            return self.sponsors_chamber_cache[url]

        page = self.get(url).text
        page = lxml.html.fromstring(page)
        title = page.xpath("//h1")[0].text_content().strip()
        chamber = self.get_chamber(title)
        self.sponsors_chamber_cache[url] = chamber

        return chamber

    # the data is utf-16, with null bytes for empty cells.
    def decode_ar_utf16(self, data) -> str:
        data = data.decode("utf-16", errors="ignore")
        data = data.replace("\x00", "")

        return data

    def get_utf_16_ftp_content(self, filename):
        path = urllib.parse.quote_plus(f"/SessionInformation/{filename}")
        url = f"https://arkleg.state.ar.us/Home/FTPDocument?path={path}"
        return self.decode_ar_utf16(self.get(url).content)
