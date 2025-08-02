import json
import time
from openocr import OpenOCR
from mss import mss
import tkinter as tk
import threading
import difflib
import numpy as np
from PIL import Image, ImageTk
import os
import sys
import psutil
import pywinctl as pwc
from rapidfuzz import process, fuzz
from collections import Counter


if getattr(sys, 'frozen', False):
    basePath = sys._MEIPASS
    os.chdir(basePath)
else:
    basePath = os.path.dirname(os.path.abspath(__file__))

def loadJson(filename):
    return json.load(open(os.path.join(basePath, filename)))

def loadSupportJson(filename):
    return json.load(open(os.path.join(basePath, 'supports', filename)))

FILTERTOGLOBAL = True


from collections import Counter

def fuzzyMatchTranscriptions(result, searchSpace,
                             topMatchesPerToken: int = 10,
                             minTokenScore: int = 30,
                             minFinalScore: int = 80):
    """
    result: list of substring tokens (e.g. ["Trainee", "Event", "Seeking", "Uniquenes"])
    searchSpace: dict mapping correct keys (strings) to their values
    topMatchesPerToken: how many fuzzy matches to pull per token
    minTokenScore: minimum per‐token fuzz.ratio score to consider
    minFinalScore: minimum fuzz.token_set_ratio score on the full query
    Returns the value for the best‐matching key, or None if no match passes thresholds.
    """
    if not result:
        return None, None

    dictKeys = list(searchSpace.keys())
    tokenMatches = []

    print('Awkward Honesty' in dictKeys)
    # 1) Fuzzy‐match each token individually
    for token in result:
        matches = process.extract(
            token,
            dictKeys,
            scorer=fuzz.ratio,
            limit=topMatchesPerToken
        )
        best = max(matches,key = lambda m: m[1])
        if best[1] > 80:
            return searchSpace[best[0]], best[0]
        print(token)
        print(matches)
        # keep only those above the token‐score threshold
        tokenMatches += [m for m in matches if m[1] >= minTokenScore]

    if not tokenMatches:
        return None, None

    # 2) Count how often each key appeared across tokens
    matchCounts = Counter(m[0] for m in tokenMatches)
    print(matchCounts)
    # rank keys by descending count
    candidates = [k for k, _ in matchCounts.most_common()]
    print(candidates)

    # 3) Final full‐string check on the top candidates
    fullQuery = "".join(result)
    finalScores = process.extract(
        fullQuery,
        candidates[:topMatchesPerToken],
        scorer=fuzz.token_set_ratio,
        limit=1
    )
    print(finalScores)
    if not finalScores:
        return None, None

    bestKey, bestScore, _ = finalScores[0]
    if bestScore < minFinalScore:
        return None, None

    return searchSpace[bestKey], bestKey

def find_window_by_process_name(proc_name):
    # 1) find the PID for your executable
    for proc in psutil.process_iter(['pid','name']):
        if proc_name.lower() in proc.info['name'].lower():
            pid = proc.info['pid']
            break
    else:
        return None

    # 2) get all top‑level windows owned by that PID
    wins = [val for val in pwc.getAllWindows() if val.getPID() == pid]
    if len(wins) == 0:
        return None
    return wins[0] 

def grab_window(window, output_path='capture.png'):
    # window.box is (left, top, width, height)
    left, top, width, height = window.box
    # print(left,top,width,height)
    with mss() as sct:
        monitor = {'left': left, 'top': top, 'width': width, 'height': height}
        sct_img = sct.grab(monitor)

    # turn into a Pillow image
    img = Image.frombytes('RGB', (sct_img.width, sct_img.height), sct_img.rgb)
    img.save(output_path)
    return output_path

def getGameArea(arr):
    width = arr.shape[1]
    return (int(width * .075),int(width * .35))
    # arr = (~np.all(arr > 200,axis=0))
    # print(arr.shape)
    # threshold = len(arr) // 30
    # padded = np.array([False] + list(arr) + [False])
    # diffs = np.diff(padded.astype(int))

    # # Start (where it goes from False to True) and end (True to False) indices
    # starts = np.where(diffs == 1)[0]
    # ends = np.where(diffs == -1)[0]

    # # Filter by threshold
    # lengths = ends - starts
    # valid = np.where(lengths >= threshold)[0]

    # if len(valid) > 0:
    #     first_idx = valid[0]
    #     start_idx = starts[first_idx]
    #     end_idx = ends[first_idx] - 1
        
    # return (start_idx,end_idx)

def fuzzymatch(transcription, supportDict, threshold=0.8):
    bestMatch = None
    bestRatio = 0.0
    for key in supportDict:
        ratio = difflib.SequenceMatcher(None, transcription.lower(), key.lower()).ratio()
        if ratio > bestRatio and ratio >= threshold:
            bestMatch = key
            bestRatio = ratio
    if bestMatch:
        return bestMatch,supportDict[bestMatch]
    return None, None



def preprocessResults(results):
    return [val['transcription'] for val in results]
    # topYs = {}
    # for val in results:
    #     topLeft, topRight, bottomRight, bottomLeft = val['points']
    #     transcription = val['transcription']
    #     roundedY = customRound(topLeft[1])
    #     if roundedY not in topYs:
    #         topYs[roundedY] = []
    #     topYs[roundedY].append(transcription)
    # return [' '.join(val) for val in topYs.values()]


def update_loop(win,engine,game):
    # sct = mss()
    currentMatch = ''
    mask = None
    while True:
        try:
            if not game.isActive:
                currentMatch = ''
                win.update_text('window not visible, please click on game')
                time.sleep(1)
                continue
            # filename = sct.shot()
            filename = grab_window(game)
            im = Image.open(filename)
            xmin,xmax = getGameArea(np.array(im.convert('L')))
            _,height = im.size
            arr = np.array(im)
            
            mask = np.zeros_like(arr)
            mask[:] = 0
            mask[height//6:height//4,xmin:xmax] = 1
            arr = np.where(mask,arr,0)
            im = Image.fromarray(arr)
            
            # im = im.crop((xmin,height//6,xmax,height//4))
            # win.set_image(np.array(im.convert('RGB')))
            im.save(filename)
            result = engine(filename)
            win.set_image(np.array(im.convert('RGB'))[height//6:height//4,xmin:xmax])
            if result is None or result[0] is None:
                win.update_text(f'Polling screen for events...\nDEBUG:\n'+'NO DETECTIONS')
                time.sleep(1)
                continue
            result = json.loads(result[0][0].split('\t')[-1])
            result = preprocessResults(result)
            # win.update_text(f"{xmin} {xmax}\n"+'\n'.join(result))
            # for val in result:
            #     event,match = fuzzymatch(val,win.searchSpace)
            match, event = fuzzyMatchTranscriptions(result,win.searchSpace)
            if match == currentMatch:
                time.sleep(2)
                continue
            if match:
                currentMatch = match
                toDisplay = f'Detected event: {event}\n'+match
                win.update_text(toDisplay)
                # win.set_image(np.array(im.convert('RGB'))[height//6:height//4,xmin:xmax])
            else:
                win.update_text(f'Polling screen for events...\nDEBUG:\n'+'\n'.join(result))
                # win.set_image(np.array(im.convert('RGB'))[height//6:height//4,xmin:xmax])
            time.sleep(.5)
        except KeyboardInterrupt:
            exit()
        except PermissionError:
            time.sleep(.5)
        # except Exception as e:
        #     print(e)
        #     time.sleep(.5)
        #     continue


class AlwaysOnTopWindow:
    def __init__(self, supports, costumes, traineeEvents,scenarioEvents):
        self.root = tk.Tk()
        self.root.title("Status")
        self.root.attributes("-topmost", True)
        self.root.resizable(True, True)
        self.root.geometry("300x300")

        self.costumes = costumes
        self.supports = supports
        self.traineeEvents = traineeEvents
        self.scenarioEvents = scenarioEvents

        # Dropdown menu
        self.dropdownVar = tk.StringVar(
            value=sorted(self.costumes, key=str.lower)[0]
        )
        dropdown = tk.OptionMenu(
            self.root,
            self.dropdownVar,
            *sorted(self.costumes, key=str.lower),
            command=self.on_dropdown_select
        )
        dropdown.pack(padx=5, pady=5)

        # -- image display area --
        self.imageLabel = tk.Label(self.root)
        self.imageLabel.pack(padx=5, pady=5)
        # keep a ref so PhotoImage doesn't get GC'd
        self._photoImage = None

        # text label
        self.labelVar = tk.StringVar()
        self.label = tk.Label(
            self.root,
            textvariable=self.labelVar,
            font=("Helvetica", 12)
        )
        self.label.pack(expand=True, fill="both", padx=5, pady=5)

        # initialize searchSpace / ids
        self.on_dropdown_select(self.dropdownVar.get())

    def on_dropdown_select(self, selection):
        ids = [str(x) for x in self.costumes[selection]]
        self.searchSpace = {}
        self.searchSpace.update(self.supports)
        self.searchSpace.update(self.traineeEvents[ids[0]])
        self.searchSpace.update(self.traineeEvents[ids[1]])
        self.searchSpace.update(self.scenarioEvents)

    def update_text(self, text):
        self.labelVar.set(text)
        self.root.update_idletasks()

        reqW = self.label.winfo_reqwidth()
        reqH = self.label.winfo_reqheight()
        padX, padY = 20, 20
        targetW = reqW + padX
        targetH = reqH + padY

        currentW = self.root.winfo_width()
        currentH = self.root.winfo_height()

        newW = max(currentW, targetW)
        newH = max(currentH, targetH)
        self.root.geometry(f"{newW}x{newH}")

    def set_image(self, npArray):
        """
        npArray: H×W×3 uint8 (or float in 0–255) RGB image.
        """
        # convert to PIL then to PhotoImage
        img = Image.fromarray(npArray.astype("uint8"), "RGB")
        currentW = self.root.winfo_width()
        factor =  currentW / npArray.shape[1] * .75
        img = img.resize((np.array(npArray.shape[:-1])[::-1] * factor).astype(int),resample=Image.Resampling.NEAREST)
        self._photoImage = ImageTk.PhotoImage(img)
        self.imageLabel.config(image=self._photoImage)

        # resize window if the image is larger
        self.root.update_idletasks()
        reqW = self.imageLabel.winfo_reqwidth()
        reqH = self.imageLabel.winfo_reqheight()
        padX, padY = 20, 20

        currentH = self.root.winfo_height()

        newW = max(currentW, reqW + padX)
        newH = max(currentH, reqH + padY)
        self.root.geometry(f"{newW}x{newH}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    
    skills = loadJson('skills.json')
    effects = loadJson('effects.json')
    traineeEvents = loadJson('traineeEvents.json')
    costumeEvents = loadJson('costumeEvents.json')
    costumes = loadJson('costumes.json')
    races = loadJson('races.json')
    scenarios = loadJson('scenarioEvents.json')
    td = {'bo':'Bond','sk': 'Skill','en':'Energy','sp':'Speed','mo':'Mood','po':'Power','pt':'Skill Points','st':'Stamina','in':'Wit','gu':'Guts','me': 'Max Energy','5s':'All Stats','se': 'Effect',\
          'sg':'Negative skill','sre': 'Skill removed','mt':'Performance token you have the least of','sga':'Star gauge','all_disc':'All discipline levels','sr':'Multiple skills possible',\
            'rc': 'Race change','sc':'Secret check','ls':'Last trained stat','fd':'Lock','fa':'Fans','stat_not_disabled':'Stat that wasnt disabled','ra':'Cancel goal','se_h':'if effect healed',\
                'se_nh':'If effect not healed','track_hint':'Relevant track hint','unspecified stats':'Stats','hp':'Remove skill','co':'If season is','bo_r':'Bond of random support cards'}
    td2 = {'ds':'Datable','ee':'End Chain','he':'Heal status','rs':'Random stat','di':'OR','nl': '\n','sl': 'If linked vvv','n':'nothing','o':'nothing','no':'nothing',\
           'result_good':"Good Result",'result_average':'Average Result','result_bad': "Bad Result",'motivation_good':'Mood >= Good','motivation_not_good': 'Mood < Good','ct':'???','rr':'Standard race rewards',\
            'other_cases':'All other cases','rl':'Cannot race','brian_tryhard':'Increase difficulty and rewards of goals','fe':'idk gametora dev wont tell me','s_nore':'idk',\
                'highest_facility':'depends on highest level facility','expensive_races':'Races cost more energy','brf':'affects next event','brp':'dependent on previous event','di_s':'','fans_minimum':'Need fans',\
                    'fans_maximum':'needs this many fans','bp2':'cant be bothered'}

    def parseChoice(c):
        acc = ''
        for val in c:
            if val['t'] in ['sc','','ps_h','ps_nh']:
                continue
            if val['t'] == 'et':
                acc += f"Event {val['d']} will occur next turn\n"
                continue
            elif val['t'] == 'rl':
                acc += f"cannot race for {val['d']} turns\n"
                continue
            if val['t'] in ['sk','sg','sre','hp']:
                skill = skills[str(val['d'])]
            elif val['t'] == 'se':
                skill = effects[str(val['d'])]
            elif val['t'] in ['rc','ra']:
                skill = races[str(val['d'])]
            elif val['t'] == 'sc':
                skill = effects[str(val['d'][1])]
            elif val['t'] == 'sr':
                for v in val['d']:
                    acc += f"{skills[str(v['d'])]} {v['v']}"
                acc += '\n'
                continue
            elif val['t'] == 'unspecified_stats':
                acc += f"{val['d']} Stats {val['v']}\n"
                continue
            elif val['t'] == 'co':
                acc += f"If season is {val['d']}\n"
                continue
            elif val['t'] == 'bo_r':
                acc+= f"Boosts bond of {val['d']} random support cards {val['v']}"
                continue
            else:
                skill = ''
            
            if val['t'] == 'fd':
                acc+= f"lock {val['d']} training options randomly"
                continue

            if val['t'] in td2:
                acc += f"{td2[val['t']]}\n"
                continue
            # print(val)
            acc += f"{td[val['t']]} {skill} {val['v'] if 'v' in val else ''} {'(Random)' if 'r' in val else ''}\n"
        return acc

    supports = {}
    traineeAndCostumeEvents = {}
    errors = set()
    for events in [traineeEvents,costumeEvents]:
        for k,v in events.items():
            traineeAndCostumeEvents[k] = {}
            for eventName, eventData in v.items():
                
                traineeAndCostumeEvents[k][eventName] = 'Top Choice:\n'+'\nBottom Choice:\n'.join([parseChoice(c) for c in eventData])

    scenarioEvents = {}
    for eventName,eventData in scenarios.items():
        try:
            scenarioEvents[eventName] = 'Top Choice:\n'+'\nBottom Choice:\n'.join([parseChoice(c) for c in eventData])
        #JP stuff
        except KeyError:
            pass
                
    

    for f in os.listdir(os.path.join(basePath, 'supports')):
        data = json.loads(loadSupportJson(f)['eventData']['en'])
        extracted = {}
        for v in data.values():
            for val in v:
                try:
                    extracted[val['n']] = 'Top Choice:\n'+'\nBottom Choice:\n'.join([parseChoice(c['r']) for c in val['c']])
                #TODO: JP stuff
                except KeyError as e:
                    pass
                    # print(f,e,val)
                    # errors.add(e)
                    # exit()
        supports.update(extracted)


    supports['Extra Training'] = f"Top Choice:\nLast trained stat +5\nEnergy -5\n(random) Heal a negative status effect\nYayoi Akikawa bond +5\nBottom Choice:\nEnergy +5"
    supports['Acupuncture (Just an Acupuncturist, No Worries! ☆)'] = 'Option 1\n\nRandomly either (~30%)\nAll stats +20\nor (~70%)\nMood -2\nAll stats -15\nGet Night Owl status\n\nOption 2\n\nRandomly either (~45%)\nObtain Corner Recovery ○ skill\nObtain Straightaway Recovery skill\nor (~55%)\nEnergy -20\nMood -2\n\nOption 3\n\nRandomly either (~70%)\nMaximum Energy +12\nEnergy +40\nHeal all negative status effects\nor (~30%)\nEnergy -20\nMood -2\nGet Practice Poor status\n\nOption 4\n\nRandomly either (~85%)\nEnergy +20\nMood +1\nGet Charming ○ status\nor (~15%)\nEnergy -10/-20\nMood -1\n(random) Get Practice Poor status\n\nOption 5\n\nEnergy +10'
    # print(len(errors))
    # exit()

    if FILTERTOGLOBAL:
        costumes = {k:v for k,v in costumes.items() if v[-1]}


    engine = OpenOCR(backend='onnx', device='cpu')
    # target = 'UmamusumePrettyDerby.exe' if sys.platform == 'win32' else 'umamusumepretty'
    win = None
    print('Looking for uma musume exe')
    while win is None:
        win = find_window_by_process_name('umamusume')
        time.sleep(1)
    print('found uma musume')



    window = AlwaysOnTopWindow(supports,costumes,traineeAndCostumeEvents,scenarioEvents)
    threading.Thread(target=update_loop, args=(window,engine,win), daemon=True).start()
    window.run()