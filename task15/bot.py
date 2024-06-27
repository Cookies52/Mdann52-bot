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

TEMPLATES = ["AMQ", "FMQ", "AM station data", "FM station data"]

def run_bot():
    edits = 3
    enwiki = pywikibot.Site("en", 'wikipedia')
    wikidata = pywikibot.Site("test", "wikidata") # ("wikidata", "wikidata")
    repo = wikidata.data_repository()

    for item in TEMPLATES:
        #template = pywikibot.Page(pywikibot.Link(item,
        #                                default_namespace=10,
        #                                source=enwiki))
    
        #transclusions = template.getReferences(only_template_inclusion=True)
        transclusions = pywikibot.pagegenerators.PagesFromPageidGenerator(["220587"])

        for page in transclusions:
            if edits == 49:
               os.exit(0)

            logger.info("Processing %s", page.title())

            wikitext = mwparserfromhell.parse(page.text)
            templates = wikitext.filter_templates(recursive=False)

            data = {}

            wikidata_item = pywikibot.ItemPage.fromPage(page)
            frequency_list = []
            fccId = []

            for item in templates:
                if item.name in TEMPLATES:
                    name = item.name
                    callsign = str(item.get(1).value)
                    logger.info("Processing callsign %s", callsign)
                    # Fetch data from the FCC site the first time we do this
                    if callsign not in data:
                        logger.info("Refreshing data from API")
                        res = s.get("https://publicfiles.fcc.gov/api/service/facility/search/" + callsign)

                        if res.status_code == 200:
                            data[callsign] = res.json()
                        else:
                            logger.error("Cannot get data for %s, received error %i", callsign, res.status_code)
                            continue

                    if data[callsign]["message"] == "No Facility Found":
                        logger.warning("Facility %s not found!", callsign)
                        # Handle as an external link as well
                        print(item)
                        if wikitext.contains("*"+str(item)) or wikitext.contains("* "+str(item)):
                            wikitext = mwparserfromhell.parse(re.sub(r"\*[ ]?"+re.escape(str(item))+"\n", "", str(wikitext)))
                        if wikitext.contains(item):
                            wikitext = mwparserfromhell.parse(re.sub(re.escape(str(item))+"\n", "", str(wikitext)))
                        continue

                    new_template = str(item)
                        
                    if new_template[2:4] == "AM":
                        for result in data[callsign]["results"]["globalSearchResults"]["amFacilityList"]:
                            if result["callSign"] == callsign:
                                frequency_list.append(result["frequency"])
                                fccId = result["id"]

                                if name == "AM station data":
                                    new_template = "{{{{AM station data|{}|{}}}}}".format(result["id"], result["callSign"])
                                else:
                                    new_template = "{{{{FCC-LMS-Facility|{}|{}}}}}".format(result["id"], result["callSign"])
                                break
                    
                    elif new_template[2:4] == "FM":
                        for result in data[callsign]["results"]["globalSearchResults"]["fmFacilityList"]:
                            if result["callSign"] == callsign:
                                frequency_list.append(result["frequency"])
                                fccId = result["id"]

                                if name == "FM station data":
                                    new_template = "{{{{FM station data|{}|{}}}}}".format(result["id"], result["callSign"])
                                else:
                                    new_template = "{{{{FCC-LMS-Facility|{}|{}}}}}".format(result["id"], result["callSign"])
                                break
                    else:
                        logger.warning("Unknown Template found : %s", new_template)

                    wikitext.replace(item, new_template)
                    item = mwparserfromhell.parse(new_template)

            # Update Wikidata using values from FCC API
            if Wikidata_Enabled:
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
                #page.save(summary="[[Wikipedia:Bots/Requests for approval/Mdann52 bot 15|Task 15]] - deleting templates AMQ/FMQ per [[Wikipedia:Templates for discussion/Log/2024 May 26#Template:AMQ|TFDs]]", minor=False)
                print(page.text[-1000:])
            time.sleep(60)


        # break

if __name__ == '__main__':
    logger.info("Starting bot run at {dt}".format(
        dt=datetime.datetime.now()
    ))
    run_bot()
