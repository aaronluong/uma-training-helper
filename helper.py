import json
import time
from openocr import OpenOCR
from mss import mss
import tkinter as tk
import threading
import difflib
import numpy as np
import cv2
from PIL import Image, ImageDraw
import shapely
import pyclipper
import rapidfuzz
import tqdm
import yaml
import onnxruntime
import os
import sys

if getattr(sys, 'frozen', False):
    basePath = sys._MEIPASS
else:
    basePath = os.path.dirname(os.path.abspath(__file__))

def loadJson(filename):
    return json.load(open(os.path.join(basePath, filename)))

def loadSupportJson(filename):
    return json.load(open(os.path.join(basePath, 'supports', filename)))

FILTERTOGLOBAL = True


def getGameArea(arr):
    arr = (~np.all(arr > 200,axis=0))
    threshold = 100
    padded = np.array([False] + list(arr) + [False])
    diffs = np.diff(padded.astype(int))

    # Start (where it goes from False to True) and end (True to False) indices
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]

    # Filter by threshold
    lengths = ends - starts
    valid = np.where(lengths >= threshold)[0]

    if len(valid) > 0:
        first_idx = valid[0]
        start_idx = starts[first_idx]
        end_idx = ends[first_idx] - 1
        
    return (start_idx,end_idx)

def fuzzymatch(transcription, supportDict, threshold=0.8):
    bestMatch = None
    bestRatio = 0.0
    for key in supportDict:
        ratio = difflib.SequenceMatcher(None, transcription.lower(), key.lower()).ratio()
        if ratio > bestRatio and ratio >= threshold:
            bestMatch = key
            bestRatio = ratio
    if bestMatch:
        return supportDict[bestMatch]
    return None

def update_loop(win,engine):
    sct = mss()
    currentMatch = ''
    while True:
        try:
            filename = sct.shot()
            # im = Image.open(filename)
            # xmin,xmax = getGameArea(np.array(im.convert('L')))
            result,_ = engine(filename)
            result = json.loads(result[0].split('\t')[-1])
            for val in result:
                match = fuzzymatch(val['transcription'],win.searchSpace)
                if match == currentMatch:
                    time.sleep(2)
                    continue
                if match:
                    currentMatch = match
                    win.update_text(match)
            time.sleep(.5)
        except KeyboardInterrupt:
            exit()
        except Exception as e:
            print(e)
            time.sleep(.5)
            continue



class AlwaysOnTopWindow:
    def __init__(self, supports,costumes,traineeEvents):
        self.root = tk.Tk()
        self.root.title("Status")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.geometry("200x400")
        self.costumes = costumes
        self.supports = supports
        self.traineeEvents = traineeEvents

        # Dropdown menu variable
        self.dropdownVar = tk.StringVar()
        self.dropdownVar.set(list(sorted(self.costumes.keys(),key = lambda val: val.lower()))[0])  # Default selection

        # Update self.ids initially
        self.ids = self.costumes[self.dropdownVar.get()]
        self.searchSpace = {}

        # Dropdown menu
        dropdown = tk.OptionMenu(self.root, self.dropdownVar, *list(sorted(self.costumes.keys())), command=self.on_dropdown_select)
        dropdown.pack(padx=5, pady=5)

        self.labelVar = tk.StringVar()
        self.label = tk.Label(self.root, textvariable=self.labelVar, font=("Helvetica", 12))
        self.label.pack(expand=True, fill='both', padx=5, pady=5)

    def on_dropdown_select(self, selection):
        self.ids = self.costumes[selection]
        self.ids = [str(val) for val in self.ids]
        self.searchSpace = {}
        self.searchSpace.update(self.supports)
        self.searchSpace.update(self.traineeEvents[self.ids[0]])
        self.searchSpace.update(self.traineeEvents[self.ids[1]])
        

    def update_text(self, text):
        self.labelVar.set(text)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    
    skills = loadJson('skills.json')
    effects = loadJson('effects.json')
    traineeEvents = loadJson('traineeEvents.json')
    costumeEvents = loadJson('costumeEvents.json')
    costumes = loadJson('costumes.json')
    td = {'bo':'Bond','sk': 'Skill','en':'Energy','sp':'Speed','mo':'Mood','po':'Power','pt':'Skill Points','st':'Stamina','in':'Wit','gu':'Guts','me': 'Maximum Energy','5s':'All Stats','se': 'Special Effect','sg':'Negative skill','mt':'Performance token you have the least of','sga':'Star gauge','all_disc':'All discipline levels','sr':'Multiple skills possible'}
    td2 = {'ds':'Datable','ee':'End Event Chain','he':'Heal negative status','rs':'Random stat boost','di':'OR','nl': '^ if not linked','sl': 'If linked vvv'}

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
    window = AlwaysOnTopWindow(supports,costumes,traineeAndCostumeEvents)
    threading.Thread(target=update_loop, args=(window,engine), daemon=True).start()
    window.run()