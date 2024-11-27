import requests
import lxml.html
import logging

def url_xpath(url, path, verify=True, user_agent=None):
    headers = {"user-agent": user_agent} if user_agent else None
    res = requests.get(url, verify=verify, headers=headers)
    try:
        doc = lxml.html.fromstring(res.text)
    except Exception as e:
        logging.error(
            f"Failed to retrieve xpath from {url} :: returned:\n"
            f"CONTENT: {res.content} \n"
            f"RETURN CODE: {res.status_code}"
        )
        raise Exception(e)
    return doc.xpath(path)

# import pdb;pdb.set_trace()
sessions = url_xpath(
    "https://apps.leg.wa.gov/billinfo/",
    '//select[@id="biennium"]/option/@value',
    verify=False,
)
print(sessions)