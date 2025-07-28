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


if getattr(sys, 'frozen', False):
    basePath = sys._MEIPASS
else:
    basePath = os.path.dirname(os.path.abspath(__file__))

def loadJson(filename):
    return json.load(open(os.path.join(basePath, filename)))

def loadSupportJson(filename):
    return json.load(open(os.path.join(basePath, 'supports', filename)))

FILTERTOGLOBAL = True

def find_window_by_process_name(proc_name):
    # 1) find the PID for your executable
    for proc in psutil.process_iter(['pid','name']):
        if proc.info['name'].lower() == proc_name.lower():
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
    print(left,top,width,height)
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
    topYs = {}
    for val in results:
        topLeft, topRight, bottomRight, bottomLeft = val['points']
        transcription = val['transcription']
        roundedY = round(topLeft[1],-1)
        if roundedY not in topYs:
            topYs[roundedY] = []
        topYs[roundedY].append(transcription)
    return [' '.join(val) for val in topYs.values()]


def update_loop(win,engine,game):
    # sct = mss()
    currentMatch = ''
    while True:
        try:
            if not game.isActive:
                print('not visible')
                currentMatch = ''
                win.update_text('window not visible, please click on game')
                time.sleep(1)
                continue
            # filename = sct.shot()
            filename = grab_window(game)
            im = Image.open(filename)
            xmin,xmax = getGameArea(np.array(im.convert('L')))
            _,height = im.size
            im = im.crop((xmin,height//6,xmax,height//4))
            # win.set_image(np.array(im.convert('RGB')))
            im.save(filename)
            result,_ = engine(filename)
            if result is None:
                win.update_text(f'Polling screen for events...\nDEBUG:\n'+'NO DETECTIONS')
                win.set_image(np.array(im.convert('RGB')))
                time.sleep(1)
                continue
            result = json.loads(result[0].split('\t')[-1])
            result = preprocessResults(result)
            # win.update_text(f"{xmin} {xmax}\n"+'\n'.join(result))
            for val in result:
                event,match = fuzzymatch(val,win.searchSpace)
                if match == currentMatch:
                    time.sleep(2)
                    break
                if match:
                    currentMatch = match
                    toDisplay = f'Detected event: {event}\n'+match
                    win.update_text(toDisplay)
                    win.set_image(np.zeros((10,10,3)))
                    break
            else:
                win.update_text(f'Polling screen for events...\nDEBUG:\n'+'\n'.join(result))
                win.set_image(np.array(im.convert('RGB')))
            time.sleep(.5)
        except KeyboardInterrupt:
            exit()
        except Exception as e:
            print(e)
            time.sleep(.5)
            continue


class AlwaysOnTopWindow:
    def __init__(self, supports, costumes, traineeEvents):
        self.root = tk.Tk()
        self.root.title("Status")
        self.root.attributes("-topmost", True)
        self.root.resizable(True, True)
        self.root.geometry("400x400")

        self.costumes = costumes
        self.supports = supports
        self.traineeEvents = traineeEvents

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
        self._photoImage = ImageTk.PhotoImage(img)
        self.imageLabel.config(image=self._photoImage)

        # resize window if the image is larger
        self.root.update_idletasks()
        reqW = self.imageLabel.winfo_reqwidth()
        reqH = self.imageLabel.winfo_reqheight()
        padX, padY = 20, 20

        currentW = self.root.winfo_width()
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
    td = {'bo':'Bond','sk': 'Skill','en':'Energy','sp':'Speed','mo':'Mood','po':'Power','pt':'Skill Points','st':'Stamina','in':'Wit','gu':'Guts','me': 'Max Energy','5s':'All Stats','se': 'Effect','sg':'Negative skill','mt':'Performance token you have the least of','sga':'Star gauge','all_disc':'All discipline levels','sr':'Multiple skills possible'}
    td2 = {'ds':'Datable','ee':'End Chain','he':'Heal status','rs':'Random stat','di':'OR','nl': '^ if not linked','sl': 'If linked vvv'}

    def parseChoice(c):
        acc = ''
        for val in c:
            if val['t'] in ['sk','sg']:
                skill = skills[str(val['d'])]
            elif val['t'] == 'se':
                skill = effects[str(val['d'])]
            elif val['t'] == 'sr':
                for v in val['d']:
                    acc += f"{skills[str(v['d'])]} {v['v']}"
                acc += 'n'
                continue
            else:
                skill = ''
            
            if val['t'] in td2:
                acc += f"{td2[val['t']]}\n"
                continue
            
            acc += f"{td[val['t']]} {skill} {val['v']} {'(Random)' if 'r' in val else ''}\n"
        return acc

    supports = {}
    traineeAndCostumeEvents = {}
    for events in [traineeEvents,costumeEvents]:
        for k,v in events.items():
            traineeAndCostumeEvents[k] = {}
            for eventName, eventData in v.items():
                try:
                    traineeAndCostumeEvents[k][eventName] = 'Top Choice:\n'+'\nBottom Choice:\n'.join([parseChoice(c) for c in eventData])
                #TODO: There's JP events I haven't implemented yet
                except KeyError:
                    pass


    for f in os.listdir(os.path.join(basePath, 'supports')):
        data = json.loads(loadSupportJson(f)['eventData']['en'])
        extracted = {}
        for v in data.values():
            for val in v:
                try:
                    extracted[val['n']] = 'Top Choice:\n'+'\nBottom Choice:\n'.join([parseChoice(c['r']) for c in val['c']])
                #TODO: Same as above
                except KeyError:
                    pass
        supports.update(extracted)


    if FILTERTOGLOBAL:
        costumes = {k:v for k,v in costumes.items() if v[-1]}


    engine = OpenOCR(backend='onnx', device='cpu')
    target = 'UmamusumePrettyDerby.exe' if sys.platform == 'win32' else 'UmamusumePrettyDerby'
    win = None
    print('Looking for uma musume exe')
    while win is None:
        win = find_window_by_process_name(target)
        time.sleep(1)
    print('found uma musume')



    window = AlwaysOnTopWindow(supports,costumes,traineeAndCostumeEvents)
    threading.Thread(target=update_loop, args=(window,engine,win), daemon=True).start()
    window.run()