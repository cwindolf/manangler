#!/usr/local/bin/python3
from numpy.random import choice, randint
from collections import defaultdict as dd
from os.path import isfile as oldme
from functools import partial
from random import shuffle
import requests
import tweepy
import ujson
import sys
from bs4 import BeautifulSoup
import pickle
from env import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_SECRET

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
# Mangle

def good_word(word):
    r = requests.get(EXISTENCE_API % word)
    json = ujson.loads(r.text)
    return '-1' not in json['query']['pages']


def random_word(dictionary):
    with open(LONGWORDS, 'r') as longwords:
        words = longwords.read().split()

    # remove the ones we've seen.
    words = [word for word in words if word not in dictionary]
    shuffle(words)

    # make sure it has a definition.
    for word in words:
        if good_word(word):
            return word

    return None


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


# I think its kind of funnier if these are intelligible.
IGNORE_THEM = {'present', 'past', 'future', 'participal', 'plural', 'singular'}

def mangle(word, transforms, dictionary):
    # Little words are too little
    if len(word) < 5 or word.lower() in IGNORE_THEM:
        return word

    # This is the learning bit
    if word in dictionary:
        return dictionary[word]

    # This is the mangling bit
    i = 0
    while i < len(word) - 5:
        fiver = word[i:i + 5]
        word = word.replace(fiver, choice(transforms)(fiver), 1)
        i += choice([1, 2])

    return word


# *************************************************************************** #
# Wiktionary parsing

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
            fourgrams, fivegrams, sixgrams, dictionary = pickle.load(oldme)
    else:
        fourgrams, fivegrams, sixgrams = init()
        dictionary = {w: w for w in IGNORE_THEM}

    # *********************************************************************** #
    # Manglers...

    transforms = [
        partial(replace, fivegrams=fivegrams),
        partial(insert, sixgrams=sixgrams),
        partial(remove, fourgrams=fourgrams)
    ]

    # *********************************************************************** #
    # Mangle...

    word = random_word(dictionary)
    if word is None:
        tweet = 'Entresh is done.'
    else:
        pos, definition = define(word)
        mangled = mangle(word, transforms, dictionary)
        tweet = mangled + ': ' + pos + '. '
        # we got 280 lol
        for part in definition.split():
            tweet += mangle(part, transforms, dictionary)
            if len(tweet) >= 279:
                break
            tweet += ' '

    # *********************************************************************** #
    # Auth...

    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth)

    try:
        stat = api.update_status(tweet)
    except TweepError as e:
        sys.stdout.write('Tweet failed.', e)
        raise

    # *********************************************************************** #
    # We learned a new word...

    dictionary[word] = mangled

    # *********************************************************************** #
    # Sleep...

    sys.stdout.write(tweet + '\n')

    with open(ME, 'wb') as newme:
            pickle.dump(
                (fourgrams, fivegrams, sixgrams, dictionary),
                newme)

    # bye!
    