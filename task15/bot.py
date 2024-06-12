import pywikibot
from pywikibot import pagegenerators
import os
import logging
import datetime
import requests
import time
from collections import OrderedDict
import mwparserfromhell
from requests.adapters import HTTPAdapter, Retry

s = requests.Session()

retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])

s.mount('http://', HTTPAdapter(max_retries=retries))

directory = os.path.dirname(os.path.realpath(__file__))

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s',
                    filename=os.path.join(directory, 'retractionbot.log'),
                    level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

TEMPLATES = ["AMQ", "FMQ", "AM station data", "FM station data"]
def run_bot():
    enwiki = pywikibot.Site("en", 'wikipedia')
    wikidata = pywikibot.Site("test", "wikidata") # ("wikidata", "wikidata")
    repo = wikidata.data_repository()

    count = 0

    for item in TEMPLATES:
        template = pywikibot.Page(pywikibot.Link(item,
                                        default_namespace=10,
                                        source=enwiki))
    
        transclusions = template.getReferences(only_template_inclusion=True)

        for page in transclusions:
            logger.info("Processing %s", page.title())
            if count == 0:
                count = 1
                continue

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
                            break

                    if data[callsign]["message"] == "No Facility Found":
                        logger.warning("Facility %s not found!", callsign)
                        break

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
                page = str(wikitext)
                page.save()

            time.sleep(60)


        # break

if __name__ == '__main__':
    logger.info("Starting bot run at {dt}".format(
        dt=datetime.datetime.now()
    ))
    run_bot()