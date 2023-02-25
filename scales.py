import pdb

import notes
from notes import Chroma, Note
from chords import Chord, chord_names, detect_sharp_preference
from util import log, test
from itertools import cycle
from collections import defaultdict
from intervals import *

# all accepted aliases for scale qualities - default suffix is listed first
key_names = defaultdict(lambda: ' (unknown key)',
   {(Maj2, Maj3, Per4, Per5, Maj6, Maj7): ['', ' major', 'maj', 'M'],
    (Maj2, Min3, Per4, Per5, Min6, Min7): ['m', ' minor', 'min', ' natural minor'],

    (Maj2, Maj3, Per4, Per5, Min6, Maj7): [' harmonic major'],
    (Maj2, Min3, Per4, Per5, Min6, Maj7): [' harmonic minor'],
    # (Maj2, Min3, Per4, Per5, Maj6, Maj7): [' melodic minor ascending'], # TBI? melodic minor descending uses the natural minor scale

    (Maj2, Maj3, Per5, Maj6): [' pentatonic', ' major pentatonic'],
    (Min3, Per4, Per5, Min7): ['m pentatonic', ' minor pentatonic'],

    (Maj2, Per4, Per5, Maj6): [' blues major', ' blues major pentatonic'],
    (Min3, Per4, Min6, Min7): [' blues minor', ' blues minor pentatonic'],

    (Min2, Maj2, Min3, Per4, Dim5, Per5, Min6, Maj6, Min7, Maj7): [' chromatic'],
    })

## dict mapping all accepted key quality names to lists of their intervals:
key_intervals = {}
# dict mapping valid whole names of keys to a tuple: (tonic, intervals)
whole_key_name_intervals = {}

for intervals, names in key_names.items():
    for key_name_alias in names:
        key_intervals[key_name_alias] = intervals
        # strip leading spaces for determining quality from string argument:
        # e.g. allow both ' minor' and 'minor',
        # so that we can parse both Key('C minor') and Key('C', 'minor')
        if len(key_name_alias) > 0 and key_name_alias[0] == ' ':
            key_intervals[key_name_alias[1:]] = intervals

        # build up whole-key-names (like 'C# minor')
        for c in notes.chromas:
            # parse both flat and sharp chroma names:
            whole_name_strings = [f'{c.sharp_name}{key_name_alias}', f'{c.flat_name}{key_name_alias}']
            if len(key_name_alias) > 0 and key_name_alias[0] == ' ':
                whole_name_strings.append(f'{c.sharp_name}{key_name_alias[1:]}')
                whole_name_strings.append(f'{c.flat_name}{key_name_alias[1:]}')

            for whole_key_name in whole_name_strings:
                whole_key_name_intervals[whole_key_name] = (c, intervals)


# circle_of_fifths = cycle(['C'])
# circle_of_fifths_minor = cycle()

class KeyChroma(Chroma):
    def __init__(self, *args, key, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(key, Key):
            self.key = key
        elif isinstance(key, str):
            self.key = Key(key)

        # inherit sharp preference from parent key:
        self.prefer_sharps = self.key.prefer_sharps
        self.name = notes.specific_chroma_name(self.position, prefer_sharps=self.prefer_sharps)

    def __add__(self, other):
        # transposing a KeyChroma stays within the same key:
        result = super().__add__(other)
        return KeyChroma(result.name, key=self.key)

    def __sub__(self, other):
        # transposing a KeyChroma stays within the same key:
        if isinstance(other, (int, Interval)):
            result = super().__sub__(other)
            return KeyChroma(result.name, key=self.key)
        else:
            assert isinstance(other, Chroma)
            # but subtracting by another chroma still just returns an interval:
            return super().__sub__(other)

class KeyChord(Chord):
    def __init__(self, *args, key, **kwargs):
        super().__init__(*args, **kwargs)

        if isinstance(key, Key):
            self.key = key
        elif isinstance(key, str):
            self.key = Key(key)

        # inherit sharp preference from parent key:
        self._set_sharp_preference(self.key.prefer_sharps)

    def __add__(self, other):
        # transposing a KeyChord stays within the same key:
        # if isinstance(other, (int, Interval)):
        result = super().__add__(other)
        return KeyChord(result.name, key=self.key)
        # else:
            # return super().__sub__(other)

    def __sub__(self, other):
        # transposing a KeyChord stays within the same key:
        if isinstance(other, (int, Interval)):
            result = super().__sub__(other)
            return KeyChord(result.name, key=self.key)
        else:
            assert isinstance(other, Chord)
            # but subtracting by another chord still just returns an interval:
            return super().__sub__(other)

class Key:
    # TBI: modes??
    def __init__(self, name, quality=None, prefer_sharps=None):
        """Initialise a Key from a name like 'D major' or 'C#m',
        or by passing a Note, Chroma, or string that can be cast to Chroma,
            (which we interpet as the key's tonic) and specifiying a quality
            like 'major', 'minor', 'harmonic', etc."""
        ### parse name:

        if quality is None: # assume major by default if quality is not given
            quality = 'major'

        # see if we can parse the first argument as a whole key name:
        if isinstance(name, str) and name in whole_key_name_intervals.keys():
            log(f'Initialising scale from whole key name: {name}')
            self.tonic, self.intervals = whole_key_name_intervals[name]
            # (we ignore the quality arg in this case)

        else:
            # get tonic from name argument:
            if isinstance(name, Chroma):
                log(f'Initialising scale from Chroma: {name}')
                self.tonic = name
            elif isinstance(name, Note):
                log(f'Initialising scale from Note: {name}')
                self.tonic = name.chroma
            elif isinstance(name, str):
                log(f'Initialising scale from string denoting tonic: {name}')
                self.tonic = Chroma(name)
            else:
                raise TypeError(f'Expected to initialise Key with tonic argument of type Chroma, Note, or str, but got: {type(name)}')
            # and get intervals from quality argument
            self.intervals = key_intervals[quality]

        # get common suffix from inverted dict:
        self.suffix = key_names[self.intervals][0]
        # and infer quality:
        self.major = (self.suffix in ['', ' pentatonic', ' blues major'])
        self.minor = (self.suffix in ['m', 'm pentatonic', ' blues minor', ' harmonic minor'])


        # figure out if we should prefer sharps or flats:
        self.prefer_sharps = detect_sharp_preference(self.tonic, self.suffix, default=True if prefer_sharps is None else prefer_sharps)

        # set tonic to use preferred sharp convention:
        self.tonic = KeyChroma(self.tonic.name, key=self)

        # and name self accordingly:
        self.name = f'{self.tonic.name}{self.suffix}'

        # form notes in scale:
        self.scale = [self.tonic]
        for i in self.intervals:
            new_chroma = self.tonic + i
            self.scale.append(new_chroma)
        # what kind of scale are we?
        if len(self) == 7:
            self.type = 'diatonic'
        elif len(self) == 5:
            self.type = 'pentatonic'
        elif len(self) == 11:
            self.type = 'chromatic'
        else:
            self.type = f'{len(self)}-tonic' #  ???

        # build up chords within scale:
        self.chords = [self.build_triad(i) for i in range(1, len(self)+1)]
        log('Initialised key: {self} ({self.scale})')

    def build_triad(self, degree: int):
        # assumed only a diatonic scale will call this method

        # scales are 1-indexed which makes it hard to modso we correct here:

        root, third, fifth = self[degree], self[degree+2], self[degree+4]
        return KeyChord([root, third, fifth], key=self)

    def get_valid_chords(self):
        # loop through all possible chords and return the ones that are valid in this key:
        chord_hash = {}

        for intervals, names in chord_names.items():
            for chroma in self.scale:
                this_chord = KeyChord(chroma, intervals, key=self)
                # is it valid? assume it is and disquality it if not
                valid = True
                for chroma in this_chord.chromas:
                    if chroma not in self.scale:
                        valid = False
                # add to our hash if it is:
                if valid:
                    if this_chord not in chord_hash:
                        chord_hash[this_chord] = 1
                    else:
                        chord_hash[this_chord] += 1

        return chord_hash

    def __contains__(self, item):
        """is this Chord or Chroma part of this key?"""
        if self.type == 'chromatic':
            return True # chromatic scale contains everything
        elif isinstance(item, Chroma):
            return item in self.scale
        elif isinstance(item, Chord):
            return item in self.chords

    def __getitem__(self, i):
        """Index scale chromas by degree (where tonic=1)"""
        if i == 0:
            raise ValueError('Scales are 1-indexed, with the tonic corresponding to [1]')

        # wrap around if given i greater than the length of the scale:
        if i > len(self):
            i = ((i - 1) % len(self)) + 1

        return self.scale[(i-1) % (len(self)+1)]

    def __call__(self, i):
        """Index scale chords by degree (where tonic=1)"""
        return self.chords[(i-1) % (len(self)+1)]

    def __str__(self):
        return f'𝄞{self.name}'

    def __repr__(self):
        return str(self)

    def __len__(self):
        return len(self.scale)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        """Keys are equal if they contain the exact same notes"""
        # obviously false if they contain different numbers of notes:
        assert isinstance(other, Key)
        if len(self) != len(other):
            return False
        else:
            log(f'Key equivalence comparison between: {self.name} and {other.name}')
            for i in range(len(self)):
                log(f'Comparing item {i+1}/{len(self)}: {self[i+1]} vs {other[i+1]}')
                if self[i+1] != other[i+1]:
                    return False # break out of loop if we detect a difference
            return True

    def __add__(self, other: int):
        """if other is an integer, move the key clockwise that many steps around the circle of fifths
        but if other is an Interval, transpose it up that many steps"""
        if isinstance(other, Interval):
            new_tonic = self.tonic + other
            return Key(f'{new_tonic.name}{self.suffix}')
        elif isinstance(other, int):
            return self.clockwise(other)
        else:
            raise TypeError('Only integers and intervals can be added to Keys')

    def __sub__(self, other):
        """if other is an integer, move the key counterclockwise that many steps around the circle of fifths
        or if other is an Interval, transpose it up that many steps
        or if other is another Key, get distance along circle of fifths"""

        if isinstance(other, (int, Interval)):
            new_tonic = self.tonic - other
            return Key(f'{new_tonic.name}{self.suffix}')
        elif isinstance(other, int):
            return self.counterclockwise(other)
        elif isinstance(other, Key):
            # circle of fifths distance
            # clockwise_distance = 0
            # found_self = False
            # for k in cycle(circle_of_fifths_clockwise):
            #     if not found_self:
            #         if k == self:
            #             found_self = True
            #             clockwise_distance = 0
            #     if found_self:
            #         if k == other:
            #             break
            #         elif clockwise_distance > 12:
            #             raise Exception('Infinite loop error')
            #         else:
            #             clockwise_distance += 1
            #
            # counterclockwise_distance = 0
            # found_self = False
            # for k in cycle(circle_of_fifths_counterclockwise):
            #     if not found_self:
            #         if k == self:
            #             found_self = True
            #             counterclockwise_distance = 0
            #     if found_self:
            #         if k == other:
            #             break
            #         elif counterclockwise_distance > 12:
            #             raise Exception('Infinite loop error')
            #         else:
            #             counterclockwise_distance += 1

            assert self.type == other.type == 'diatonic'
            self_pos = co5s_positions[self]
            other_pos = co5s_positions[other]
            clockwise_distance = (other_pos - self_pos) % 12
            counterclockwise_distance = (self_pos - other_pos) % 12

            return min([abs(clockwise_distance), abs(counterclockwise_distance)])

    def clockwise(self, value=1):
        """fetch the next key from clockwise around the circle of fifths,
        or if value>1, go clockwise that many steps"""
        reference_key = self if self.major else self.relative_major()
        new_co5s_pos = (co5s_positions[reference_key] + value) % 12
        # instantiate new key object: (just in case???)
        new_key = co5s[new_co5s_pos]
        new_key = new_key if self.major else new_key.relative_minor()
        return Key(new_key.tonic, new_key.suffix)

    def counterclockwise(self, value=1):
        return self.clockwise(-value)

    def relative_minor(self):
        assert not self.minor, f'{self} is already minor, and therefore has no relative minor'
        rm_tonic = notes.relative_minors[self.tonic]
        return Key(rm_tonic, 'minor')

    def relative_major(self):
        assert not self.major, f'{self} is already major, and therefore has no relative major'
        rm_tonic = notes.relative_majors[self.tonic]
        return Key(rm_tonic)

# circle_of_fifths_clockwise = { 0: Key('C')}
# for i in range(11):
#     cur_key = circle_of_fifths_clockwise[-1]
#     cur_key = circle_of_fifths_clockwise.append(cur_key + 7)
# circle_of_fifths_counterclockwise = {Key('C')}
# for i in range(11):
#     cur_key = circle_of_fifths_counterclockwise[-1]
#     cur_key = circle_of_fifths_counterclockwise.append(cur_key - 7)

# construct circle of fifths:
circle_of_fifths = {0: Key('C')}
for i in range(1,12):
    circle_of_fifths[i] = list(circle_of_fifths.values())[-1] + PerfectFifth
co5s = circle_of_fifths

circle_of_fifths_positions = {value:key for key,value in co5s.items()}
co5s_positions = circle_of_fifths_positions

# by semitone, not degree
scale_semitone_names = {0: "tonic", # 1st
                        2: "supertonic", # 2nd
                        3: "mediant", # 3rd (minor)
                        4: "mediant", # 3rd (major)
                        5: "subdominant", # 4th
                        7: "dominant", # 5th
                        8: "submediant", # 6th (minor)
                        9: "submediant", # 6th (major)
                        10: "subtonic", # 7th (minor)
                        11: "leading tone", # 7th (major)
                        }


C = Key('C')
Cm = Key('Cm')

Db = Cs = Key('Db')
Csm = Dbm = Key('C#m')

D = Key('D')
Dm = Key('Dm')

Eb = Ds = Key('Eb')
Ebm = Dsm = Key('Ebm')

E = Key('E')
Em = Key('Em')

F = Key('F')
Fm = Key('Fm')

Gb = Fs = Key('Gb')
Fsm = Gbm = Key('F#m')

G = Key('G')
Gm = Key('Gm')

Ab = Gs = Key('Ab')
Gsm = Abm = Key('G#m')

A = Key('A')
Am = Key('Am')

Bb = As = Key('Bb')
Bbm = Asm = Key('Bbm')

B = Cb = Key('B')
Bm = Key('Bm')