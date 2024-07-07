import pywikibot
from pywikibot import pagegenerators
import os
import logging
import datetime
import pywikibot.pagegenerators
import requests
import time
from collections import OrderedDict
import mwparserfromhell
from requests.adapters import HTTPAdapter, Retry
import re
import csv
import sys

s = requests.Session()

retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])

s.mount('http://', HTTPAdapter(max_retries=retries))
s.headers.update({'User-Agent': 'Mdann52 bot (https://en.wikipedia.org/wiki/User:Mdann52-bot; mailto:matthewdann52@gmail.com)'})

directory = os.path.dirname(os.path.realpath(__file__))

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename=os.path.join(directory, 'retractionbot.log'),
                    level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

Wikidata_Enabled = False

fm_temp = ["FMQ", "FM station data", "LPFM station data"]
TEMPLATES = ["FMQ", "AM station data", "FM station data", "AMQ"]

def run_bot():
    edits = 0
    enwiki = pywikibot.Site("en", 'wikipedia')
    wikidata = pywikibot.Site("wikidata", "wikidata")
    repo = wikidata.data_repository()

    callsign_data = {}   

    # Update offline data
    with open("facility.dat") as f:
    
        csv_reader = csv.DictReader(f, delimiter='|', quotechar='"')
        for item in csv_reader:
            callsign_data[item["callsign"]] = item
            callsign_data[item["callsign"]]["callSign"] = item["callsign"]
            callsign_data[item["callsign"]]["id"] = item["facility_id"]


    for item in TEMPLATES:
        template = pywikibot.Page(pywikibot.Link(item,
                                        default_namespace=10,
                                        source=enwiki))
    
        transclusions = template.getReferences(only_template_inclusion=True)

        for page in transclusions:
            wikidata_item = None
            logger.info("Processing %s", page.title())

            wikitext = mwparserfromhell.parse(page.text)
            templates = wikitext.filter_templates(recursive=True)

            data = {}

            if page.namespace() == 0:
               wikidata_item = pywikibot.ItemPage.fromPage(page)
            else:
                print(page.namespace())

            frequency_list = []
            fccId = []

            for item in templates:
                if item.name.strip() in TEMPLATES:
                    name = item.name.strip()
                    callsign = str(item.get(1).value)
                    if re.match(r"[0-9]", callsign[0]) is not None:
                        continue
                    logger.info("Processing callsign %s", callsign)
                    # Fetch data from the FCC site the first time we do this
                    if callsign not in data:
                        logger.info("Refreshing data from API")
                        res = s.get("https://publicfiles.fcc.gov/api/service/facility/search/" + callsign)

                        if res.status_code == 200:
                            data[callsign] = res.json()
                        else:
                            logger.error("Cannot get data for %s, received error %i", callsign, res.status_code)

                    new_template = None

                    if data[callsign]["message"] == "No Facility Found":
                        logger.warning("Facility %s not found!", callsign)
                        # Handle as an external link as well
                        if callsign in callsign_data:
                            if callsign_data[callsign]["service_code"][0] == "F":
                                data[callsign]["results"]["globalSearchResults"]["fmResultsCount"] += 1
                                data[callsign]["results"]["globalSearchResults"]["fmFacilityList"] = [callsign_data[callsign]]
                            if callsign_data[callsign]["service_code"][0] == "A":
                                data[callsign]["results"]["globalSearchResults"]["amResultsCount"] += 1
                                data[callsign]["results"]["globalSearchResults"]["amFacilityList"] = [callsign_data[callsign]]

                    if name[:2] == "AM" and data[callsign]["results"]["globalSearchResults"]["amResultsCount"] != 0:
                        for result in data[callsign]["results"]["globalSearchResults"]["amFacilityList"]:
                            if result["callSign"] == callsign or result["callSign"] == callsign+"-AM":
                                frequency_list.append(result["frequency"])
                                fccId = result["id"]

                                if name == "AM station data":
                                    new_template = "{{{{AM station data|{}|{}}}}}".format(result["id"], result["callSign"])
                                else:
                                    new_template = "{{{{FCC-LMS-Facility|{}|{}}}}}".format(result["id"], result["callSign"])
                                break
                    
                    if name in fm_temp and data[callsign]["results"]["globalSearchResults"]["fmResultsCount"] != 0:
                        for result in data[callsign]["results"]["globalSearchResults"]["fmFacilityList"]:
                            if result["callSign"] == callsign or result["callSign"] == callsign+"-FM":
                                frequency_list.append(result["frequency"])
                                fccId = result["id"]

                                if name == "FM station data":
                                    new_template = "{{{{FM station data|{}|{}}}}}".format(result["id"], result["callSign"])
                                else:
                                    new_template = "{{{{FCC-LMS-Facility|{}|{}}}}}".format(result["id"], result["callSign"])
                                break
                    if name[:2] not in ["FM", "AM"]:
                        logger.warning("Unknown Template found : %s", name)

                    if new_template is None:
                        # If we don't find it in the db, remove the entry.
                        if wikitext.contains("*"+str(item)) or wikitext.contains("* "+str(item)):
                             wikitext = mwparserfromhell.parse(re.sub(r"\*[ ]?"+re.escape(str(item))+"\n", "", str(wikitext)))
                        if wikitext.contains(item):
                            wikitext.replace(item, None)
                        continue

                    new_template = mwparserfromhell.parse(new_template).get(0)

                    if item.has(2):
                        new_template.add(3, item.get(2))
                    if wikitext.contains(item):
                        wikitext.replace(item, new_template)
                    item = mwparserfromhell.parse(new_template)

                elif item.name.strip() == "RadioTranslators":
                    if item.has("call1"):
                        cs = item.get("call1").value.strip()
                        if cs in callsign_data:
                            item.add("fid1", callsign_data[cs]["facility_id"])
                    if item.has("call2"):
                        cs = item.get("call2").value.strip()
                        if cs in callsign_data:
                            item.add("fid2", callsign_data[cs]["facility_id"])
                    if item.has("call3"):
                        cs = item.get("call3").value.strip()
                        print(cs)
                        if cs in callsign_data:
                            item.add("fid3", callsign_data[cs]["facility_id"])
                    if item.has("call4"):
                        cs = item.get("call4").value.strip()
                        if cs in callsign_data:
                            item.add("fid4", callsign_data[cs]["facility_id"])
                    if item.has("call5"):
                        cs = item.get("call5").value.strip()
                        if cs in callsign_data:
                            item.add("fid5", callsign_data[cs]["facility_id"])
                    if item.has("call6"):
                        cs = item.get("call6").value.strip()
                        print(cs)
                        if cs in callsign_data:
                            item.add("fid6", callsign_data[cs]["facility_id"])
                    if item.has("call7"):
                        cs = item.get("call7").value.strip()
                        if cs in callsign_data:
                            item.add("fid7", callsign_data[cs]["facility_id"])
                    if item.has("call8"):
                        cs = item.get("call8").value.strip()
                        if cs in callsign_data:
                            item.add("fid8", callsign_data[cs]["facility_id"])
                    if item.has("call9"):
                        cs = item.get("call9").value.strip()
                        print(cs)
                        if cs in callsign_data:
                            item.add("fid9", callsign_data[cs]["facility_id"])  

            # Update Wikidata using values from FCC API
            if Wikidata_Enabled and wikidata_item is not None:
                claims = wikidata_item.get()["claims"]
                if 'P2144' in claims:
                    logger.warning("Claim for 'P2144' already exists, skipping")
                else:
                    for f in frequency_list:
                        freqclaim = pywikibot.Claim(repo, u'P2144') #Frequency
                        freqclaim.setTarget(f)
                        wikidata_item.addClaim(freqclaim, summary=u'Adding frequency from FCC API.')

                if 'P2317' in claims:
                    logger.warning("Claim for 'P2317' already exists, skipping")
                else:
                    callClaim = pywikibot.Claim(repo, u'P2317') #callsign
                    callClaim.setTarget(callsign)
                    wikidata_item.addClaim(callClaim, summary=u'Adding callsign from FCC API.')

                if 'P1400' in claims:
                    logger.warning("Claim for 'P1400' already exists, skipping")
                else:
                    idClaim = pywikibot.Claim(repo, u'P1400') #FCC ID
                    idClaim.setTarget(fccId)
                    wikidata_item.addClaim(idClaim, summary=u'Adding FCC ID from FCC API.')
            
            logger.info("Finished processing %s", page.title())
            if str(wikitext) != page:
                page.text = str(wikitext)
                page.save(summary="[[Wikipedia:Bots/Requests for approval/Mdann52 bot 15|Task 15]] - deleting templates AMQ/FMQ per [[Wikipedia:Templates for discussion/Log/2024 May 26#Template:AMQ|TFDs]]", minor=False)
            time.sleep(5)


        # break

if __name__ == '__main__':
    logger.info("Starting bot run at {dt}".format(
        dt=datetime.datetime.now()
    ))
    run_bot()
