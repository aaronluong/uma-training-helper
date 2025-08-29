import shutil
import os
from pathlib import Path
from urllib.parse import urlparse, unquote, urlsplit
import mimetypes
import hashlib

from playwright.sync_api import sync_playwright
import json
import time
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import regex as re
from datetime import datetime
import requests
import html



def safeName(urlPath: str) -> str:
    # turn a URL path+query into a safe filename
    parsed = urlsplit(urlPath)
    path = unquote(parsed.path)
    if path.endswith("/") or path == "":
        path = path + "index"
    base = path.lstrip("/").replace("/", "_")
    if parsed.query:
        qhash = hashlib.sha1(parsed.query.encode()).hexdigest()[:10]
        base = f"{base}__{qhash}"
    return base

def extFor(contentType: str) -> str:
    if not contentType:
        return ""
    ext = mimetypes.guess_extension(contentType.split(";")[0].strip()) or ""
    # common overrides
    if contentType.startswith("application/javascript"):
        return ".js"
    if contentType.startswith("text/javascript"):
        return ".js"
    return ext

def savePageWithAssets(url: str, outDir: str):
    outPath = Path(outDir)
    outPath.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # collect responses as they arrive
        saved = set()

        def handleResponse(resp):
            try:
                reqUrl = resp.url
                # skip data: blobs, etc.
                if reqUrl.startswith("data:"):
                    return
                ct = resp.headers.get("content-type", "")
                body = resp.body()  # bytes
                name = safeName(urlparse(reqUrl).path + ("?" + urlparse(reqUrl).query if urlparse(reqUrl).query else ""))
                ext = extFor(ct)
                target = outPath / f"{name}{ext}"
                target.parent.mkdir(parents=True, exist_ok=True)
                if target in saved:
                    return
                target.write_bytes(body)
                saved.add(target)
            except Exception:
                pass  # ignore failures (CORS, blocked, etc.)

        page.on("response", handleResponse)

        page.goto(url, wait_until="networkidle")
        # save final DOM as our index
        (outPath / "index.html").write_text(page.content(), encoding="utf-8")

        browser.close()

# Example:
# savePageWithAssets("https://example.com/page", "saved_page")

# Example:
# savePage("https://example.com/page")
if os.path.exists('testgpt_files'):
    shutil.rmtree('testgpt_files')
savePageWithAssets('https://gametora.com/umamusume/characters','testgpt_files')

def findEnd(s):
    s = s.replace('\\','').replace("'",'')
    start = s[0]
    if start == '{':
        count = 1
        acc = '{'
        for c in s[1:]:
            if c == '}':
                count -= 1
            elif c == '{':
                count += 1
            acc += c
            if count ==0:
                break

    elif start == '[':
        count = 1
        acc = '['
        for c in s[1:]:
            if c == ']':
                count -= 1
            elif c == '[':
                count += 1
            acc += c
            if count ==0:
                break

    return acc


text = open('cardlist.htm').read()
pattern = r'href="https://gametora\.com/umamusume/supports/([^"]*)"'
matches = re.findall(pattern, text)
matches[:5]

def fetchBuildId(pageUrl="https://gametora.com/umamusume/characters"):
    r = requests.get(pageUrl, timeout=15)
    r.raise_for_status()
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        raise RuntimeError("Couldn't find __NEXT_DATA__ on the page.")
    nextDataRaw = html.unescape(m.group(1))
    nextData = json.loads(nextDataRaw)
    return nextData["buildId"]

buildId = fetchBuildId()
linkify = lambda val: f'https://gametora.com/_next/data/{buildId}/umamusume/supports/{val}.json?id={val}'
matches = [val[0] for val in sorted([[name,datetime.strptime(json.load(open(f'supports/{name}.json'))['itemData']['release'],r'%Y-%m-%d')] for name in matches],key = lambda val: val[1])]

for match in tqdm(matches):
    
    # if 'release' not in json.load(open(f'supports/{match}.json'))['itemData']:
    #     print(match)
    if 'release_en' in open(f'supports/{match}.json').read():
        continue
    
    result = requests.get(linkify(match))
    data = json.loads(result.content)['pageProps']
    if 'release_en' not in data['itemData']:
        break
    json.dump(data,open(f'supports/{match}.json','w'))
    time.sleep(.5)

    
jsFolder = 'testgpt_files'
for f in os.listdir(jsFolder):
    if '.js' not in f:
        continue
    t = open(os.path.join(jsFolder,f)).read()
    if len(t.split('name_en')) > 1000:
        payload = t
        break
else:
    raise ValueError


matches = re.finditer(r'JSON\.parse\((["\'])(.*?)\1\)', payload, re.DOTALL)
for val in matches:
    rawString = val.group(2)
    

    try:
        # first attempt: maybe it's already valid JSON
        parsed = json.loads(rawString)
    except json.JSONDecodeError:
        # fallback: unescape then parse
        cleaned = rawString.encode('utf-8').decode('unicode_escape')
        parsed = json.loads(cleaned)
    if 'Shooting' in rawString:
        skills = {val['id']:val['name_en'] if 'name_en' in val else val['enname'] for val in parsed}
        json.dump(skills,open('skills.json','w'))
    elif 'migraine' in rawString.lower():
        effects = {val['id']:val['name_en'] if 'name_en' in val else val['name_en_eon'] for val in parsed}
        json.dump(effects,open('effects.json','w'))
    elif 'Bakushin for Love!' in rawString:
        m = {0:'t',1:'v',2:'d',3:'r'}
        costumeEvents = {}
        for character in parsed:
            id,data = character
            costumeEvents[id] = {}
            # if 'bakushin' not in str(data).lower():
            #     continue
            for val in data:
                jpname,*event = val
                
                if event[-1][0] == 103:

                    eventName = event[-1][-1]
                else:
                    eventName = jpname
                costumeEvents[id][eventName] = []
                options = [val[-1] for val in event[0]]
                # print(options)
                for i,opt in enumerate(options):
                    # print(i+1)
                    temp = []
                    for stat in opt:
                        d = {}
                        for i,val in enumerate(stat):
                            if val is None:
                                continue
                            k = m[i]
                            d[k] = val
                        temp.append(d)
                    costumeEvents[id][eventName].append(temp)
        # print(costumeEvents)
        json.dump(costumeEvents,open('costumeEvents.json','w'))                    
    elif 'The Bakushin Book!' in rawString:
        traineeEvents = {}
        for character in parsed:
            id,special,choice,date,val1,val2 = character
            traineeEvents[id] = {}
            # print(val2)
            for l in [choice,date,val1]:
                for val in l:
                    jpname,*event = val
                
                    if event[-1][0] == 103:

                        eventName = event[-1][-1]
                    else:
                        eventName = jpname
                
                    traineeEvents[id][eventName] = []
                    options = [val[-1] for val in event[0]]
                    # print(options)
                    for i,opt in enumerate(options):
                        # print(i+1)
                        temp = []
                        for stat in opt:
                            d = {}
                            for i,val in enumerate(stat):
                                if val is None:
                                    continue
                                k = m[i]
                                d[k] = val
                            temp.append(d)
                        traineeEvents[id][eventName].append(temp)
            if len(val2) > 0:
                traineeEvents[id][val2[-1][2]] = [[{'t':'en','v':'+10'},{'t':'pt','v':'+5'}],[{'t':'en','v':'+30'},{'t':'pt','v':'+10'},{'t':'di'},{'t':'en','v':'+30'},{'t':'pt','v':'+10'},{'t':'sp','v':'-5'},{'t':'po','v':'+5'},{'t':'se','d':'4'}]]
            traineeEvents[id]['Dance Lesson'] = [[{'t':val,'v':'+10'}] for val in special[1]]
            traineeEvents[id]["New Year's Resolutions"] = [[val] for val in [{'t':special[0],'v':'+10'},{'t':'en','v':'+20'},{'t':'pt','v':'+20'}]]
            traineeEvents[id]["New Year's Shrine Visit"] = [[val] for val in [{'t':'en','v':'+30'},{'t':'5s','v':'+5'},{'t':'pt','v':'+35'}]]
            traineeEvents[id]["At Summer Camp (Year 2)"] = [[{'t':'po','v':'+10'}],[{'t':'gu','v':'+10'}]]
        json.dump(traineeEvents,open('traineeEvents.json','w'))
    elif 'Exhilarating' in rawString:
        m = ['t','v','d','r']
        scenarioEvents = {}
        for scenario in parsed:
            eventsWithChoices = scenario[1]
            for event in eventsWithChoices:
                name = event[-1][-1] if event[-1][0] == 103 else event[0]
                choices = [val[1] for val in event[1]]
                processed = []
                for choice in choices:
                    temp = []
                    for result in choice:
                        data = {}
                        for i in range(len(result)):
                            data[m[i]] = result[i]
                        temp.append(data)
                    processed.append(temp)
                scenarioEvents[name] = processed
            # break
        json.dump(scenarioEvents,open('scenarioEvents.json','w'))
for f in os.listdir(jsFolder):
    if '.js' not in f:
        continue
    t = open(os.path.join(jsFolder,f)).read()
    if len(t.split('costume')) > 100:

        costumes = json.loads(t.split('JSON.parse(')[1][1:-7].replace('\\',''))
        costumes = {f"{val['name_en']} ({val['version']})" if 'version' in val else val['name_en'] : (val['char_id'],val['costume'], 'release_en' in val )  for val in costumes}
        json.dump(costumes,open('costumes.json','w'))
        break
else:
    raise ValueError

for f in os.listdir(jsFolder):
    if '.js' not in f:
        continue
    text = open(os.path.join(jsFolder,f)).read()
    if len(text.split('en_name')) > 100:
        sub = text.split('JSON.parse(')[1][1:-7]

        parsed = json.loads(sub.replace('\\',''))
        d = {val['char_id']:val['en_name'] if 'en_name' in val else val['jp_name'] for val in parsed}
        json.dump(d,open('charIds.json','w'))
        break
else:
    raise ValueError

for f in os.listdir(jsFolder):
    if not f.endswith('.js'):
        continue
    text = open(os.path.join(jsFolder,f)).read()
    if 'hanshin-juvenile' not in text:
        continue
    print(f)
    sub = text.split('JSON.parse(')[3][1:-45]
    parsed = json.loads(findEnd(sub.replace('\\','')))
    d = {val['id']:val['name_en'] if 'name_en' in val else val['name_jp'] for val in parsed}
    # print(d)
    json.dump(d,open('races.json','w'))
    break
else:
    raise ValueError