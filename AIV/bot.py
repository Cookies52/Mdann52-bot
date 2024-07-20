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
   'Wikipedia:Usernames for administrator attention/Bot'
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

    page = pywikibot.Page(enwiki, title="User:HBC AIV helperbot/Special IPs")
    for line in page.text.split("\n"):
        if line != '' and line[0] == ";":
            d = line.strip(";").split(":",1)
            if d[0] != '':
                for address in ipaddress.ip_network(d[0]):
                    special_ips[str(address)] = d[1]
        elif line[0:14] == "* [[:Category:":
            special_cats.append(line[5:-2])


while True:
    get_ip_list()
    for pagetitle in pages_to_watch:
        try:
            print(pagetitle)
            removed = 0
            to_remove = []
            page = pywikibot.Page(enwiki, title=pagetitle)
            content = mwparserfromhell.parse(page.text)
            # Calculate users left
            all_temps = content.filter_templates()
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
                    partialBlock = True

                    # check tags
                    if "<!--marked-->" not in f:
                        if userInfo.isAnonymous():
                            if username in special_ips:
                                content.replace(f, f+"<!--marked-->\n:*'''Note:''' "+special_ips[username] + ". ~~~~")
                                page.text = content
                                page.save(minor=False, summary=str(vandalCount)+" reports remaining. Commenting on " + username + " : Sensitive IP ([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])")
                                break
                        # Get user categories
                        for cat in userInfo.categories():
                            if cat.title() in special_cats:
                                content.replace(f, f+"<!--marked-->\n:*'''Note:''' User is in the category: "+ cat + ". ~~~~")
                                page.text = content
                                page.save(minor=False, summary=str(vandalCount)+" reports remaining. Commenting on " + username + " : User is in the category " + cat +  "([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])")
                                break

                    if userInfo.is_blocked() or (not userInfo.isAnonymous() and userInfo.is_locked()):
                        anon_only = False
                        props = userInfo.getprops()
                        block_info=None
                        if userInfo.isAnonymous():
                            block_info = enwiki.blocks(iprange=username)
                            # check if user in special groups
                            for block in block_info:
                                if 'anononly' in block:
                                    anon_only = True
                        else:
                            block_info = enwiki.blocks(users=username)
                        for b in block_info:
                            if "partial" not in b:
                                partialBlock = False
                        if partialBlock:
                            continue
                        counter = idx
                        while counter < len(lines):
                            if lines[counter] == "":
                                counter += 1

                            if lines[counter] == f or lines[counter][0:2] == "*:" or lines[counter][0] == ":":
                                if counter == len(lines)-1:
                                    content.remove(lines[counter])
                                else:
                                    content.remove(lines[counter]+"\n")
                                counter += 1
                            elif lines[counter] == "*\n":
                                content.remove(lines[counter])
                                counter += 1
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
                        if "blocknocreate" or "nocreate" in props:
                            flags.append("ACB")
                        if anon_only:
                            flags.append("AO")

                        if len(flags) != 0:
                            summary += " ([[User:HBC AIV helperbot/Legend|" + " ".join(flags) + "]])"
                        summary += " ([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])"
                        print(summary)
                        page.text = content
                        page.save(summary=summary, minor=False)
                        time.sleep(5)
                        break

            page = pywikibot.Page(enwiki, title=pagetitle)
            content = mwparserfromhell.parse(page.text)
            all_temps = mwparserfromhell.parse(content).filter_templates()
            vandals = [t for t in all_temps if t.name.lower() in ["vandal", "ipvandal", "user-uaa"]]
            vandalCount = len(vandals)
            for t in all_temps:
                if t.name == "noadminbacklog":
                    if vandalCount >= 4:
                        newt = mwparserfromhell.nodes.Template(name="adminbacklog")
                        newt.add("bot", "HBC AIV helperbot14")
                        content.replace(t, newt)
                        page.text = content
                        page.save(summary=str(vandalCount)+" reports remaining. Noticeboard is backlogged ([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])")
                if t.name == "adminbacklog":
                    if vandalCount <= 2:
                        newt = mwparserfromhell.nodes.Template(name="noadminbacklog")
                        newt.add("bot", "HBC AIV helperbot14")
                        content.replace(t, newt)
                        page.text = content
                        page.save(summary=str(vandalCount)+" reports remaining. Noticeboard is no longer backlogged ([[Wikipedia:Bots/Requests for approval/HBC AIV helperbot14|under trial]])")
        except Exception as e:
            print(type(e).__name__, e)
            continue 
   
    time.sleep(60)
