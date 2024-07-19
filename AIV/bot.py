import pywikibot
import time
import mwparserfromhell
import ipaddress

import pywikibot.logentries
import pywikibot.pagegenerators

pages_to_watch = [
   'Wikipedia:Administrator intervention against vandalism',
   'Wikipedia:Administrator intervention against vandalism/TB2',
   'Wikipedia:Usernames for administrator attention',
   'Wikipedia:Usernames for administrator attention/Bot',
#  'User:HBC AIV helperbot5/sandbox' => 10
]

IP_Sections = [
    "== Listed at [[Wikipedia:Sensitive IP addresses]] =="
]

Cat_Section = [
    "== Sockpuppet related ==",
    "== Misc ==",
    "== Shared =="
]

enwiki = pywikibot.Site("en", 'wikipedia')
special_ips = {}
special_cats = []
instructions = []

def get_ip_list():
    print("Fetching special IP list")
    special_ips = {}
    special_cats = []

    page = pywikibot.Page(enwiki, title="User:HBC AIV helperbot/Special IPs")
    parse = mwparserfromhell.parse(page.text)
    for section in parse.get_sections(levels=[2]):
        if section.get(0) in IP_Sections:
            for item in section.split("\n")[2:-1]:
                d = item.strip(";").split(":",1)
                if d[0] != '':
                    for address in ipaddress.ip_network(d[0]):
                        special_ips[str(address)] = d[1]
        elif section.get(0) in Cat_Section:
            print("CAT")
            for item in section.split("\n")[2:-1]:
                print(item[2:])
                if item != '':
                    special_cats.append(item[2:])
        else:
            print("ERR")

while True:
    #get_ip_list()
    for pagetitle in pages_to_watch:
      print(pagetitle)
      try:
        removed = 0
        to_remove = []
        page = pywikibot.Page(enwiki, title=pagetitle)
        content = mwparserfromhell.parse(page.text)
        # Calculate users left
        all_temps = mwparserfromhell.parse(content).filter_templates()
        vandals = [t for t in all_temps if t.name.lower() in ["vandal", "ipvandal", "user-uaa"]]
        vandalCount = len(vandals)

        lines = page.text.split("\n")
        for idx, f in enumerate(lines):
            temps = mwparserfromhell.parse(f).filter_templates()
            v = [t for t in temps if t.name.lower() in ["vandal", "ipvandal", "user-uaa"]]
            for t in v:
                username = str(t.get("1"))
                if username[0:2] == "1=":
                  username = username[2:]
                    
                userInfo = pywikibot.User(enwiki, username)

                if userInfo.is_blocked():
                    props = userInfo.getprops()
                    content.remove(f+"\n")
                    counter = idx
                    while counter < len(lines):
                        counter += 1
                        if lines[counter][0:2] == "*:":
                            content.remove(lines[counter]+"\n")
                        else:
                            break

                    vandalCount -= 1
                    flags = []
                    summary = str(vandalCount) + " users left, rm [[Special:Contributions/" + username +"|" + username + "]]"
                    if "blockedby" in props and props["blockedby"] != "":
                        if "blockexpiry" in props and props["blockexpiry"] == "infinite":
                            summary += " (blocked indef by " + props["blockedby"]
                        else:
                            summary += " (blocked by " + props["blockedby"]
                        summary += ")"

                    if "blockowntalk" in props:
                        flags.append("TPD")
                    if "blockemail" in props:
                        flags.append("EMD")
                    if "blocknocreate" in props:
                        flags.append("ACB")

                    if len(flags) != 0:
                        summary += " ([[User:HBC AIV helperbot/Legend|" + " ".join(flags) + "]])"
                    summary += " ([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])"
                    print(summary)
                    page.text = content
                    page.save(summary=summary, minor=False)
                    time.sleep(5)
                    break
        for t in all_temps:
            if t.name == "noadminbacklog":
                if vandalCount > 4:
                    newt = mwparserfromhell.nodes.Template(name="adminbacklog")
                    newt.add("bot", "HBC AIV helperbot14")
                    content.replace(t, newt)
                    page.text = content
                    page.save(summary=str(vandalCount)+" reports remaining. Noticeboard is backlogged")
            if t.name == "adminbacklog":
                if vandalCount < 2:
                    newt = mwparserfromhell.nodes.Template(name="noadminbacklog")
                    newt.add("bot", "HBC AIV helperbot14")
                    content.replace(t, newt)
                    page.text = content
                    page.save(summary=str(vandalCount)+" reports remaining. Noticeboard is no longer backlogged")
      except Exception as e:
          print(e)
          continue    
    time.sleep(60)