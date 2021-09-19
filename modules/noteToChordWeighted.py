import json
import pandas as pd
import argparse
import time
import itertools
import pickle

with open("../modules/json_files/keychorddict.json") as f:
    data = json.load(f)
with open("../modules/pickle_files/key_chord_name_mapping.pickle", "rb") as f:
    key_chord_name_mapping = pickle.load(f)
for k in data:
    data[k]["key"] = data[k]["key"].upper()


def intersection(a, b):
    temp = set(b)
    c = [value for value in a if value in temp]
    return c


def edit_distance(a, b):
    if abs(len(a) - len(b)) >= 2:
        return 999
    if len(a) > len(b):
        a = a[:-1]
    if len(b) > len(a):
        b = b[:-1]
    dist = 0
    for i, val in enumerate(a):
        dist += abs(val - b[i])
    ###Scoring function
    return dist


def ScoringModule(
    input_idx,
    input_name,
    input_dict,
    chord_idx,
    chord_name,
    ed,
    length_match,
    chord,
    ismajor,
):
    score = 0
    for i, idx in enumerate(input_idx):
        if idx in chord_idx:
            score += 100 * input_dict[input_name[i]]
    for i, name in enumerate(input_name):
        if name in chord_name:
            score += 1000 * input_dict[input_name[i]]
    if chord_name[0] in input_name:  # root is contained
        score += 500 * input_dict[chord_name[0]]
    if chord_name[0] == input_name[0]:  # root is first
        score += 10 * input_dict[chord_name[0]]
    score += 60 // (ed + 1)
    if not length_match:
        score -= 100
    if ismajor:
        if chord in ["I"]:  # Tonic function chords
            score += 5
        elif chord == "VI":
            score += 4
        elif chord in ["IV", "II"]:  # Predominant function chords
            score += 3
        elif chord in ["V", "VII"]:  # Dominant function chords
            score += 2
    else:
        if chord in ["I", "VI"]:
            score += 4
        elif chord in ["IV", "II"]:  # Predominant function chords
            score += 3
        elif chord in ["V", "VII"]:  # Dominant function chords
            score += 2
    return score


def MatchAnalysis(input_idx, input_name, chord_idx, chord_name, chord):
    idxMatch = intersection(input_idx, chord_idx)
    nameMatch = intersection(input_name, chord_name)
    if chord_name[0] in input_name:
        root_match = True
    else:
        root_match = False
    if chord_name[0] == input_name[0]:
        root_first = True
    else:
        root_first = False
    ed = edit_distance(input_idx, chord_idx)
    if len(input_idx) != len(chord_idx):
        length_match = False
    else:
        length_match = True
    return len(idxMatch), len(nameMatch), root_match, ed, length_match, root_first


key_mapping = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# key_list to number_list
def keys2num(keys):
    # 1 by 1 key to number
    def key2num(key):
        key = key.upper()
        num = key_mapping[key[0]]
        modifier = len(key)
        if modifier == 1:
            return num
        elif key[1] == "#":
            return (num + (modifier - 1)) % 12
        elif key[1] == "B" or key[1] == "-":
            return (num - (modifier - 1)) % 12
        elif key[1] == "X":
            return (num + (modifier - 1) * 2) % 12

    if keys[-1] == "-":
        return [key2num(key) for key in keys[:-1]]
    else:
        return [key2num(key) for key in keys]


def NoteToChord(keys_dict, key=None, numOut=10, threshold=2):
    """
        This is a weighted version.
        keys_dict will be a dictionary, notes as key, value as weight.
        Value should be normalized (add up to 1)
    """

    if numOut is None:
        numOut = 10
    if threshold is None:
        threshold = 2
    if key is not None:
        key = key.upper()

    keys_name = list(keys_dict.keys())
    keys_idx = keys2num(keys_name)
    sorted_keys = sorted(keys_idx)

    possible_chords = set()
    sorted_keys = list(set(sorted_keys))
    for i in range(threshold, 5):
        for each in itertools.combinations(sorted_keys, i):
            possible_chords.update(key_chord_name_mapping[str(each)])
    chords = list(possible_chords)
    if chords == []:
        return None, None

    rscore = []  # -1 for temp in range(len(chords))]
    rchord = []
    ridxMatch = []
    rnameMatch = []
    rrootMatch = []
    reditdist = []
    rlengthMatch = []
    numOk = 0
    for idx, chord in enumerate(chords):
        entry = data[chord]
        if (
            key is None or entry["key"] == key
        ):  ## remeber to make all key upper() after import**********\
            if entry["key"].upper().find("MAJOR") != -1:
                ismajor = True
            else:
                ismajor = False
            (
                idxMatch,
                nameMatch,
                rootMatch,
                ed,
                length_match,
                root_first,
            ) = MatchAnalysis(
                keys_idx, keys_name, entry["idx"], entry["naming"], entry["chord"]
            )
            score = ScoringModule(
                keys_idx,
                keys_name,
                keys_dict,  # for retrieving weight
                entry["idx"],
                entry["naming"],
                ed,
                length_match,
                entry["chord"],
                ismajor,
            )
            rscore.append(score)
            rchord.append(chord)
            ridxMatch.append(idxMatch)
            rnameMatch.append(nameMatch)
            rrootMatch.append(rootMatch)
            reditdist.append(ed)
            rlengthMatch.append(length_match)
            numOk += 1

    rscore, rchord, ridxMatch, rnameMatch, rrootMatch, reditdist, rlengthMatch = zip(
        *sorted(
            zip(
                rscore,
                rchord,
                ridxMatch,
                rnameMatch,
                rrootMatch,
                reditdist,
                rlengthMatch,
            ),
            reverse=True,
        )[: min(numOk, numOut)]
    )
    # format output
    result = []
    for idx in range(len(rscore)):
        result.append(
            {
                "Chord": rchord[idx],
                "Score": rscore[idx],
                "pitch match": ridxMatch[idx],
                "name match": rnameMatch[idx],
                "root present": rrootMatch[idx],
                "edit distance": reditdist[idx],
                "length match": rlengthMatch[idx],
            }
        )
    return result


if __name__ == "__main__":
    start = time.time()
    result = NoteToChord(
        {"C": 0.3, "E": 0.025, "A": 0.3, "F": 0.3, "G": 0.05, "B": 0.025}, "Cmajor"
    )
    end = time.time()
    print("Time taken:", end - start, "\n", result)

