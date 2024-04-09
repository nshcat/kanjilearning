import requests
import json
from typing import List, Dict
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from itertools import zip_longest
import os
import os.path
from enum import IntFlag
import romkan
import argparse

class StyleOptions(IntFlag):
    Nothing = 0x0
    BigKanji = 0x1
    ShowRomaji = 0x2
    ShowRegularKanji = 0x4
    CrossGuide = 0x8
    ShowDictionary = 0x10
    
style: StyleOptions
style = StyleOptions.Nothing

from itertools import zip_longest
def grouper(n, iterable, fillvalue=None):
    "grouper(3, 'ABCDEFG', 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(fillvalue=fillvalue, *args)


class KanjiDictionaryEntry(object):
    _word: str
    _translations: List[str]

    def __init__(self, word: str, translations: List[str]):
        self._word = word
        self._translations = translations

    @property
    def word(self) -> str:
        return self._word

    @property
    def translations(self) -> List[str]:
        return self._translations


class KanjiData(object):
    _symbol: str
    _readings_on: List[str]
    _readings_kun: List[str]
    _stroke_diagram_file: str
    _meanings: List[str]
    _dictionaryEntries: List[KanjiDictionaryEntry]

    def __init__(self, sym: str) -> None:
        self._symbol = sym
        self._stroke_diagram_file = "%05x" % ord(self._symbol[0])
        self._readings_kun = []
        self._readings_on = []
        self._meanings = []
        self._dictionaryEntries = []

    @property
    def symbol(self) -> str:
        return self._symbol
    
    @property
    def stroke_diagram_file(self) -> str:
        return self._stroke_diagram_file
    
    @property
    def kun_readings(self) -> List[str]:
        return self._readings_kun

    @kun_readings.setter
    def kun_readings(self, val: List[str]):
        self._readings_kun = val

    @property
    def on_readings(self) -> List[str]:
        return self._readings_on
    
    @on_readings.setter
    def on_readings(self, val: List[str]):
        self._readings_on = val

    @property
    def meanings(self) -> List[str]:
        return self._meanings
    
    @meanings.setter
    def meanings(self, val: List[str]):
        self._meanings = val

    @property
    def dictionary_entries(self) -> List[KanjiDictionaryEntry]:
        return self._dictionaryEntries

    @dictionary_entries.setter
    def dictionary_entries(self, val: List[KanjiDictionaryEntry]):
        self._dictionaryEntries = val

def render_write_cell(pdf: FPDF, cell_width: float):
    if StyleOptions.CrossGuide in style:
        pdf.set_draw_color(188, 188, 188)
        pdf.line(pdf.x, pdf.y + (cell_width/2), pdf.x + cell_width, pdf.y + (cell_width/2))
        pdf.line(pdf.x + (cell_width/2), pdf.y, pdf.x + (cell_width/2), pdf.y + cell_width)

    pdf.set_draw_color(0, 0, 0)
    pdf.cell(cell_width, cell_width, border=1)

def render_readings(pdf: FPDF, cell_width: float, readings: List[str]):
    if len(readings) == 0:
        pdf.cell(cell_width * 3, cell_width, text="none", border=1, align='C')
    else:
        kana_readings = ", ".join(readings)
        romaji_readings = ", ".join([romkan.to_roma(reading) for reading in readings])
        pdf.multi_cell(cell_width * 3, cell_width, text=kana_readings + "\n" + romaji_readings, border=1, align='C', max_line_height=cell_width/2,
                       new_x=XPos.RIGHT, new_y=YPos.TOP)

def render_meaning_block(pdf: FPDF, kanji: KanjiData, cell_width: float, cells: int):
    meaningText = ", ".join([x.capitalize() for x in kanji.meanings])
    #pdf.cell(cell_width * cells, cell_width, txt=meaningText, border=1, align='C')
    pdf.multi_cell(cell_width * cells, cell_width, text=meaningText, border=1, align='C', max_line_height=cell_width/2,
                   new_x=XPos.RIGHT, new_y=YPos.TOP)

def render_dictionary_sub_block(pdf: FPDF, entries: List[KanjiDictionaryEntry], column: int, cell_width: float):
    originX, originY = pdf.get_x() + (column * (cell_width * 4)), pdf.get_y()

    paddingSize = cell_width / 10

    pdf.set_x(originX + paddingSize)
    pdf.set_y(originY + paddingSize)

    textLineHeight = cell_width / 4
    for dictionaryEntry in entries:
        if dictionaryEntry is None:
            break

        pdf.set_x(originX + paddingSize)
        pdf.set_font('NotoSansJP', 'B', 8)
        pdf.cell(cell_width * 3, textLineHeight, border=0, text=dictionaryEntry.word, new_x=XPos.LEFT, new_y=YPos.NEXT)

        pdf.set_x(originX + paddingSize)
        pdf.set_font('NotoSansJP', '', 8)
        translations = "; ".join(dictionaryEntry.translations)
        pdf.cell(cell_width * 3, textLineHeight, border=0, text=translations, new_x=XPos.LEFT, new_y=YPos.NEXT)

        pdf.set_y(pdf.get_y() + paddingSize)

def render_dictionary_block(pdf: FPDF, kanji: KanjiData, cell_width: float):
    # Remember position of top left corner of dictionary border cell
    oldX, oldY = pdf.get_x(), pdf.get_y()

    paddingSize = cell_width / 10
    textLineHeight = cell_width / 4
    height = (min(3, len(kanji.dictionary_entries)) * (2*textLineHeight + paddingSize)) + (2*paddingSize)

    # Draw dictionary border cell
    pdf.cell(cell_width * 12, height, border=1)

    # We can fit three columns of three entries each.
    columns = list(grouper(3, kanji.dictionary_entries))[:3]
    for i in range(len(columns)):
        pdf.set_x(oldX), pdf.set_y(oldY)
        render_dictionary_sub_block(pdf, columns[i], i, cell_width)

    # Return to origin of the dictionary block cell so that we can cleanly
    # jump to the end of the block (since the amount of content varies depending on the kanji, but
    # the dictionary cell stays the same size)
    pdf.set_x(oldX), pdf.set_y(oldY)
    pdf.ln(height)

def calc_kanji_block_height(kanji: KanjiData, cell_width: float) -> float:
    baseHeight = (cell_width * 4) if StyleOptions.BigKanji in style else (cell_width * 3)

    # Spacer between entries
    baseHeight += 0.25*cell_width

    if StyleOptions.ShowDictionary in style and len(kanji.dictionary_entries) > 0:
        paddingSize = cell_width / 10
        textLineHeight = cell_width / 4
        additionalHeight = ((2*textLineHeight + paddingSize) * min(len(kanji.dictionary_entries), 3)) + (paddingSize * 2)
    else:
        additionalHeight = 0

    return baseHeight + additionalHeight

def render_kanji_block(pdf: FPDF, kanji: KanjiData, cell_width: float):
    pdf.set_font('NotoSansJP', '', 12)

    if StyleOptions.ShowRegularKanji in style:
        pdf.set_font('NotoSansJP', '', 24)
        pdf.cell(cell_width * 1, cell_width, text=kanji.symbol, border=1, align='C')
              
        pdf.set_font('NotoSansJP', 'B', 12)
        render_meaning_block(pdf, kanji, cell_width, 5)
    else: 
        pdf.set_font('NotoSansJP', 'B', 12)
        render_meaning_block(pdf, kanji, cell_width, 6)

    pdf.set_font('NotoSansJP', 'B', 12)
    render_readings(pdf, cell_width, kanji.on_readings)
    render_readings(pdf, cell_width, kanji.kun_readings)
    pdf.ln(cell_width)

    kanjiBlockSize = 3 if StyleOptions.BigKanji in style else 2

    pdf.cell(cell_width*kanjiBlockSize, cell_width*kanjiBlockSize, border=1, new_x=XPos.LEFT)

    stroke_path = os.path.join(os.getcwd(), "kanji", kanji.stroke_diagram_file + ".png")

    if os.path.exists(stroke_path):
        pdf.image(name=stroke_path, x=pdf.x, y=pdf.y, w=cell_width*kanjiBlockSize, h=cell_width*kanjiBlockSize, keep_aspect_ratio=True)
    else:
        pdf.cell(cell_width*kanjiBlockSize, cell_width*kanjiBlockSize, border=1)

    numWriteCellsInX = 9 if StyleOptions.BigKanji in style else 10

    pdf.set_x(cell_width*(kanjiBlockSize + 0.5))
    for _ in range(numWriteCellsInX):
        render_write_cell(pdf, cell_width)

    pdf.ln(cell_width)
    pdf.set_x(cell_width*(kanjiBlockSize + 0.5))
    for _ in range(numWriteCellsInX):
        render_write_cell(pdf, cell_width)

    # Render third row of writing cells for big kanji mode, since kanji stroke diagram is 3x3
    if StyleOptions.BigKanji in style:
        pdf.ln(cell_width)
        pdf.set_x(cell_width*(kanjiBlockSize + 0.5))
        for _ in range(numWriteCellsInX):
            render_write_cell(pdf, cell_width)


    if StyleOptions.ShowDictionary in style and len(kanji.dictionary_entries) > 0:
        pdf.ln(cell_width)
        render_dictionary_block(pdf, kanji, cell_width)
        pdf.ln(cell_width * 0.25)
    else:
        pdf.ln(cell_width * 1.25)


def applyOverrides(kanjis: List[KanjiData]):
    from overrides import overrides
    for kanji in kanjis:
        if kanji.symbol in overrides:
            override = overrides[kanji.symbol]
            if override.meanings is not None:
                kanji.meanings = override.meanings
            if override.on is not None:
                kanji.on_readings = override.on
            if override.kun is not None:
                kanji.kun_readings = override.kun

def renderDocument(kanjis: List[KanjiData], path: str) -> None:
    pdf = FPDF()
    # NOTE: Fonts need to be put into the "font" folder inside site-packages\fpdf! (Folder might not exist yet)
    pdf.add_font('NotoSansJP', '', 'NotoSansJP-Regular.ttf')
    pdf.add_font('NotoSansJP', 'B', 'NotoSansJP-Bold.ttf')
    pdf.set_font('NotoSansJP', '', 14)

    # 5 Kanjis per page
    cell_width = (pdf.w / 13) # Padded on left and right by a half cell
    pdf.l_margin = cell_width / 2
    pdf.t_margin = cell_width / 2

    availHeightPerPage = pdf.h - cell_width # Half cell width padding on top and bottom

    heightLeft = availHeightPerPage
    pdf.add_page()

    for kanji in kanjis:
        kanjiBlockHeight = calc_kanji_block_height(kanji, cell_width)

        # Do we need a new page?
        if heightLeft < kanjiBlockHeight:
            pdf.add_page()
            heightLeft = availHeightPerPage

        render_kanji_block(pdf, kanji, cell_width)

        heightLeft -= kanjiBlockHeight

    #if StyleOptions.ShowDictionary in style:
    #    kanjisPerPage = 2 if StyleOptions.BigKanji in style else 3
    #else:
    #    kanjisPerPage = 4 if StyleOptions.BigKanji in style else 5

    #for pagekanjis in grouper(kanjisPerPage, kanjis):
    #    pdf.add_page()
    #    for kanji in pagekanjis:
    #        if kanji is None:
    #            break
    #        render_kanji_block(pdf, kanji, cell_width)

    pdf.output(path)


def parseKanjiDictEntries(dictionaryEntries: List[object]) -> List[KanjiDictionaryEntry]:
    dictEntries: List[KanjiDictionaryEntry] = []

    for entry in dictionaryEntries:
        try:
            word, translations = entry
            if len(translations) > 0:
                dictEntries.append(KanjiDictionaryEntry(word, list(translations)))

        except Exception as ex:
            print("Failed to parse kanji dictionary entry, skipping: %s" % str(ex))
            continue

    return dictEntries
def lookupKanjiSymbolsDict(dictionaryPath: str, kanjiSyms: List[str]) -> List[KanjiData]:
    kanjiDict : Dict[str, KanjiData]
    kanjiDict = {}
    
    with open(dictionaryPath, encoding="utf8") as file:
        jsonObj = json.load(file)
        
        for kanjiEntry in jsonObj:
            try:
                if len(kanjiEntry) == 4:
                    kanjiSymbol, meanings, kunReadings, onReadings = kanjiEntry
                    rawDictionaryEntries = []
                else:
                    kanjiSymbol, meanings, kunReadings, onReadings, rawDictionaryEntries = kanjiEntry
                
                kanji = KanjiData(kanjiSymbol)
                kanji.kun_readings = kunReadings
                kanji.on_readings = onReadings
                kanji.meanings = meanings
                kanji.dictionary_entries = parseKanjiDictEntries(rawDictionaryEntries)
                
                kanjiDict[kanjiSymbol] = kanji
                
            except Exception as ex:
                print("Failed to read kanji, ignoring: %s" % str(ex))

    kanjiData : List[KanjiData]
    kanjiData = []
    for kanjiSym in kanjiSyms:
        if kanjiSym not in kanjiDict:
            print("Kanji %s not present in dictionary, ignoring" % kanjiSym)
            continue
        else:
            kanjiData.append(kanjiDict[kanjiSym])
            
    return kanjiData

    
def lookupKanjiSymbolsAPI(kanjiSyms: List[str]) -> List[KanjiData]:
    kanjis : List[KanjiData] = [] 

    for kanjisym in kanjiSyms:
        kanji = KanjiData(kanjisym)
        r = requests.get("https://kanjiapi.dev/v1/kanji/%s" % kanjisym, {})
        content = json.loads(r.content)
        kanji.kun_readings = content["kun_readings"][:3]
        kanji.on_readings = content["on_readings"][:3]
        kanji.meanings = [x for x in content["meanings"] if "radical" not in x and "counter" not in x][:3] 
        kanjis.append(kanji)

    return kanjis

def fetchGradeKanjis(grade: int) -> List[str]:
    r = requests.get(f"https://kanjiapi.dev/v1/kanji/grade-{grade}", {})
    kanjilist = json.loads((r.content.decode('utf-8')))
    return kanjilist
    

def loadKanjiFile(path: str) -> List[KanjiData]:
    with open(path, encoding="utf8") as file:
        jsonObj = json.load(file)    
        return list(jsonObj)
        
     
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="output file name")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--grade", help="retrieve kanjis from given grade list", type=int, required=False)
    group.add_argument("--file", help="retrieve kanjis from given file", required=False)
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dictionary-file", help="use dictionary file as information source", required=False)
    group.add_argument("--api", help="use kanji API as information source", required=False, action="store_true")
    
    parser.add_argument("-B", "--big-kanji", help="enable bigger kanji box", action="store_true")
    parser.add_argument("-K", "--show-kanji", help="enable non-stylized kanji in addition to stroke diagram", action="store_true")
    parser.add_argument("-C", "--cross-guide", help="enable cross writing guide in kanji boxes", action="store_true")
    parser.add_argument("-D", "--show-dictionary", help="enable dictionary display", action="store_true")
    args = parser.parse_args()

    if args.big_kanji:
        style |= StyleOptions.BigKanji
        
    if args.show_kanji:
        style |= StyleOptions.ShowRegularKanji

    if args.cross_guide:
        style |= StyleOptions.CrossGuide

    if args.show_dictionary:
        style |= StyleOptions.ShowDictionary

    kanjiSyms: List[str]
    kanjiSyms = None
    
    kanjis: List[KanjiData]
    kanjis = None

    if args.grade is not None:
        print(f"Fetching kanjis from grade {args.grade} list")
        kanjiSyms = fetchGradeKanjis(args.grade)   
    elif args.file is not None:
        print(f"Fetching kanjis from file {args.file}")
        kanjiSyms = loadKanjiFile(args.file)
    else:
        print("No input option supplied!")
        raise SystemExit(-1)
        
        
    if args.api:
        print("Looking up kanji info via Kanji API")
        kanjis = lookupKanjiSymbolsAPI(kanjiSyms)
    elif args.dictionary_file is not None:
        print("Looking up kanji info via dictionary file")
        kanjis = lookupKanjiSymbolsDict(args.dictionary_file, kanjiSyms)
    else:
        print("No information source provided!")
        raise SystemExit(-1)
        
    # applyOverrides(kanjis)
    
    print(f"Retrieved {len(kanjis)} kanji.")

    print(f"Rendering to {args.output}")
    renderDocument(kanjis, args.output)


    
    

    
