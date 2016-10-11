from numpy.random import choice, randint
from collections import defaultdict as dd
from os.path import isfile as oldme
from functools import partial
import requests
import ujson
from bs4 import BeautifulSoup
import pickle


# Storage
ME = 'state.pickle'
WORDS = 'words'
LONGWORDS = 'longwords'

# API format string
EXISTENCE_API = 'https://en.wiktionary.org/w/api.php?action=query&titles=%s&format=json'
DEFN_API = 'http://en.wiktionary.org/w/index.php?title=%s&printable=yes'


# *************************************************************************** #
# Save and Load program state between runs

def save():
    pass


def load():
    pass


# *************************************************************************** #
# Do the work

def zero():
    return 0


def ngrams(n):
    ngs = dd(zero)
    with open(LONGWORDS, 'r') as longwords:
        for word in longwords:
            word = word.strip()
            for i in range(len(word) - n):
                ngram = word[i:i + n]
                ngs[ngram] += 1
    return ngs


def init():
    # Compute 4-,5-,6-grams
    return [ngrams(n) for n in [4, 5, 6]]


# *************************************************************************** #
# Profit

def good_word(word):
    r = requests.get(EXISTENCE_API % word)
    json = ujson.loads(r.text)
    return '-1' not in json['query']['pages']

def random_word(done):
    with open(LONGWORDS, 'r') as longwords:
        words = longwords.read().split()
    while True:
        word = choice(words)
        if word not in done and good_word(word):
            return word


def sum_sxor(a_string, b_string):
    acc = 0
    for a, b in zip(a_string, b_string):
        if a == b:
            acc += 1
    return acc


def replace(fivegram, fivegrams):
    possibles = []
    beg, *mid, end = fivegram
    for replacement in fivegrams.keys():
        rbeg, *rmid, rend = replacement
        if rbeg == beg and sum_sxor(mid, rmid) in {1, 2} and rend == end:
            possibles.append(replacement)
    possibles.sort(key=lambda x: fivegrams[x])
    if possibles:
        # print(fivegram, '-->', possibles[0])
        return possibles[0]
    return fivegram


def insert(fivegram, sixgrams):
    possibles = []
    a, b, c, d, e = fivegram
    for sixgram in sixgrams:
        if (a == sixgram[0]
            and b == sixgram[1]
            and d == sixgram[-2]
            and e == sixgram[-1]
            and c in sixgram[2:-2]):
            possibles.append(sixgram)
    possibles.sort(key=lambda x: sixgrams[x])
    if possibles:
        # print(fivegram, '-->', possibles[0])
        return possibles[0]
    return fivegram


def remove(fivegram, fourgrams):
    possibles = []
    a, b, c, d, e = fivegram
    for fourgram in fourgrams:
        w, x, y, z = fourgram
        if w == a and z == e:
            # only allow removing `c`
            if x == b and y == d:
                possibles.append(fourgram)
    possibles.sort(key=lambda x: fourgrams[x])
    if possibles:
        # print(fivegram, '-->', possibles[0])
        return possibles[0]
    return fivegram


def mangle(word, transforms):
    if len(word) < 5:
        return word
    i = 0
    while i < len(word) - 5:
        fiver = word[i:i + 5]
        word = word.replace(fiver, choice(transforms)(fiver), 1)
        i += 1
    return word


# *************************************************************************** #
# Grab and mangle definitions from Wiktionary

def define(word):
    r = requests.get(DEFN_API % word)
    soup = BeautifulSoup(r.text, 'html.parser')
    try:
        definition = (soup.html
                          .body
                          .find(id='content')
                          .find(id='bodyContent')
                          .find(id='mw-content-text')
                          .ol
                          .li
                          .text)
        pos = (soup.html
                  .body
                  .find(id='content')
                  .find(id='bodyContent')
                  .find(id='mw-content-text')
                  .ol
                  .find_previous_sibling('h3')
                  .text)
    except AttributeError:
        return None, None
    return pos.strip(), ' '.join(definition.split())


# *************************************************************************** #
if __name__ == '__main__':
    # *********************************************************************** #
    # Waking up... for the first time?

    if oldme(ME):
        with open(ME, 'rb') as oldme:
            fourgrams, fivegrams, sixgrams, done = pickle.load(oldme)
    else:
        fourgrams, fivegrams, sixgrams = init()
        done = []

    # *********************************************************************** #
    # Manglers...

    transforms = [
        partial(replace, fivegrams=fivegrams),
        partial(insert, sixgrams=sixgrams),
        partial(remove, fourgrams=fourgrams)
    ]

    # *********************************************************************** #
    # Mangle...

    word = random_word(done)
    pos, definition = define(word)
    mangled = mangle(word, transforms)
    mangled_pos = mangle(pos, transforms)
    mangled_def = ' '.join(mangle(part, transforms) for part in definition.split())

    print(mangled + ': ' + mangled_pos + '.', mangled_def)

    with open(ME, 'wb') as newme:
            pickle.dump((fourgrams, fivegrams, sixgrams, done + [word]), newme)

    