"""
This file defines functions for importing the CA database dumps in mysql.

The workflow is:
 - Drop & recreate the local capublic database.
 - Inspect the site with regex and determine which files have been updated, if any.
 - For each such file, unzip it & call import.
"""
import os
import re
import glob
import os.path
import subprocess
import logging
import lxml.html
import argparse
from datetime import datetime

# from os.path import join, split
# from functools import partial
from collections import namedtuple

import requests
import MySQLdb


MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")

BASE_URL = "https://downloads.leginfo.legislature.ca.gov/"


# ----------------------------------------------------------------------------
# Logging config
logger = logging.getLogger("openstates.ca-update")
# logger.setLevel(logging.INFO)

# ch = logging.StreamHandler()
# formatter = logging.Formatter('%(asctime)s - %(message)s',
#                               datefmt='%H:%M:%S')
# ch.setFormatter(formatter)
# logger.addHandler(ch)

# ---------------------------------------------------------------------------
# Miscellaneous db admin commands.


def clean_text(s):
    # replace smart quote characters
    s = re.sub(r"[\u2018\u2019]", "'", s)
    s = re.sub(r"[\u201C\u201D]", '"', s)
    s = s.replace("\xe2\u20ac\u02dc", "'")
    return s


def db_drop():
    """Drop the database."""
    logger.info("dropping capublic...")

    try:
        connection = MySQLdb.connect(
            host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASSWORD, db="capublic"
        )
    except MySQLdb._exceptions.OperationalError:
        # The database doesn't exist.
        logger.info("...no such database. Bailing.")
        return

    connection.autocommit(True)
    cursor = connection.cursor()

    cursor.execute("DROP DATABASE IF EXISTS capublic;")

    connection.close()
    logger.info("...done.")


# ---------------------------------------------------------------------------
# Functions for updating the data.
DatRow = namedtuple(
    "DatRow",
    [
        "bill_version_id",
        "bill_id",
        "version_num",
        "bill_version_action_date",
        "bill_version_action",
        "request_num",
        "subject",
        "vote_required",
        "appropriation",
        "fiscal_committee",
        "local_program",
        "substantive_changes",
        "urgency",
        "taxlevy",
        "bill_xml",
        "active_flg",
        "trans_uid",
        "trans_update",
    ],
)


def dat_row_2_tuple(row):
    """Convert a row in the bill_version_tbl.dat file into a
    namedtuple.
    """
    cells = row.split("\t")
    res = []
    for cell in cells:
        if cell.startswith("`") and cell.endswith("`"):
            res.append(cell[1:-1])
        elif cell == "NULL":
            res.append(None)
        else:
            res.append(cell)
    return DatRow(*res)


def encode_or_none(value):
    return value.encode() if value else None


def load_bill_versions(connection):
    """
    Given a data folder, read its BILL_VERSION_TBL.dat file in python,
    construct individual REPLACE statements and execute them one at
    a time. This method is slower that letting mysql do the import,
    but doesn't fail mysteriously.
    """

    sql = """
        REPLACE INTO capublic.bill_version_tbl (
            BILL_VERSION_ID,
            BILL_ID,
            VERSION_NUM,
            BILL_VERSION_ACTION_DATE,
            BILL_VERSION_ACTION,
            REQUEST_NUM,
            SUBJECT,
            VOTE_REQUIRED,
            APPROPRIATION,
            FISCAL_COMMITTEE,
            LOCAL_PROGRAM,
            SUBSTANTIVE_CHANGES,
            URGENCY,
            TAXLEVY,
            BILL_XML,
            ACTIVE_FLG,
            TRANS_UID,
            TRANS_UPDATE)

        VALUES (%s)
        """
    sql = sql % ", ".join(["%s"] * 18)

    cursor = connection.cursor()
    with open("BILL_VERSION_TBL.dat") as f:
        for row in f:
            # The files are supposedly already in utf-8, but with
            # copious bogus characters.
            row = clean_text(row)
            row = dat_row_2_tuple(row)
            with open(row.bill_xml) as f:
                text = f.read()
                text = clean_text(text)
                row = row._replace(bill_xml=text)
                cursor.execute(sql, [encode_or_none(column) for column in row])

    cursor.close()


def load(folder):
    """
    Load .dat files in the given folder using Python and manual inserts.
    This avoids MySQL LOAD DATA issues and Docker crashes.
    """
    logger.info("Loading data from %s using Python inserts..." % folder)
    os.chdir(folder)

    connection = MySQLdb.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        passwd=MYSQL_PASSWORD,
        db="capublic",
    )
    connection.autocommit(True)
    cursor = connection.cursor()

    for filepath in glob.glob("*.dat"):
        table_name = filepath.replace(".dat", "").lower()

        if table_name == "bill_version_tbl":
            logger.info("Using special handler for bill_version_tbl")
            load_bill_versions(connection)
            continue

        logger.info(f"Inserting rows into {table_name} from {filepath}")
        with open(filepath) as f:
            for line in f:
                values = [
                    None if v == "NULL" else v.strip("`")
                    for v in line.strip().split("\t")
                ]
                placeholders = ", ".join(["%s"] * len(values))
                sql = f"REPLACE INTO capublic.{table_name} VALUES ({placeholders})"
                try:
                    cursor.execute(sql, values)
                except Exception as e:
                    logger.error(f"Failed to insert into {table_name}: {e}")
                    continue

    cursor.close()
    connection.close()
    os.chdir("..")
    logger.info("All .dat files loaded")


def db_create():
    """Create the database"""

    logger.info("Creating capublic...")

    dirname = get_zip("pubinfo_load.zip")
    os.chdir(dirname)

    with open("capublic.sql") as f:
        # Note: apparently MySQLdb can't execute compound SQL statements,
        # so we have to split them up.
        sql_statements = f.read().split(";")

    connection = MySQLdb.connect(
        host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASSWORD
    )
    print(
        f"mysql connection host={MYSQL_HOST}, user={MYSQL_USER}, password={MYSQL_PASSWORD}"
    )
    connection.autocommit(True)
    cursor = connection.cursor()

    # MySQL warns in OCD fashion when executing statements relating to
    # a table that doesn't exist yet. Shush, mysql...
    import warnings

    warnings.filterwarnings("ignore", "Unknown table.*")

    for sql in sql_statements:
        cursor.execute(sql)

    cursor.close()
    connection.close()
    os.chdir("..")


def get_contents():
    resp = {}
    html = requests.get(BASE_URL, verify=False).text
    doc = lxml.html.fromstring(html)
    # doc.make_links_absolute(BASE_URL)
    rows = doc.xpath("//table/tr")
    for row in rows[2:]:
        date = row.xpath("string(td[3])").strip()
        if date:
            date = datetime.strptime(date, "%Y-%m-%d %H:%M")
            filename = row.xpath("string(td[2]/a[1]/@href)")
            resp[filename] = date
    return resp


def _check_call(*args):
    logging.info("calling " + " ".join(args))
    subprocess.check_call(args)


def get_zip(filename):
    dirname = filename.replace(".zip", "")
    _check_call("wget", "--no-check-certificate", BASE_URL + filename)
    _check_call("rm", "-rf", dirname)
    _check_call("unzip", filename, "-d", dirname)
    _check_call("rm", "-rf", filename)
    return dirname


def get_data(contents, year):
    newest_file = "2000"
    newest_file_date = datetime(2000, 1, 1)
    files_to_get = []

    if year:
        files_to_get.append(f"pubinfo_{year}.zip")
    else:
        # get file for latest date
        for filename, date in contents.items():
            date_part = filename.replace("pubinfo_", "").replace(".zip", "")
            if date_part.startswith("daily") and date > newest_file_date:
                newest_file = filename
                newest_file_date = date
        files_to_get.append(newest_file)

    for file in files_to_get:
        dirname = get_zip(file)
        load(dirname)


if __name__ == "__main__":
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument("--year", action="store", type=int)
    args = my_parser.parse_args()
    year = args.year

    db_drop()
    db_create()
    contents = get_contents()
    get_data(contents, year)
