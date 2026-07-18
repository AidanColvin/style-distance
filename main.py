from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path
from typing import Optional
import json
import re
import string
import sys

weights = {
    "average_word_length": 11,
    "different_to_total": 33,
    "exactly_once_to_total": 50,
    "average_sentence_length": 0.4,
    "average_sentence_complexity": 4
}

def split_string(text: str, delimiters: str) -> list[str]:
    """
    given a string and a set of delimiters 
    return list of substrings 
    split at any delimiter 
    whitespace removed
    """
    parts = re.split(f"[{re.escape(delimiters)}]", text)
    return [p.strip() for p in parts if p.strip()]

def split_into_sentences(text: str) -> list[str]:
    """
    given a text string
    return list of sentences
    split at . ! or ?
    """
    return split_string(text, ".!?")

def split_into_phrases(sentence: str) -> list[str]:
    """
    given a sentence string
    return list of phrases
    split at , ; or :
    """
    return split_string(sentence, ",;:")

def clean_word(word: str) -> str:
    """
    given a string representing a single word, return "cleaned" version 
    punctuation removed 
    converted to lowercase
    """
    return word.strip(string.punctuation).lower()

def get_clean_words(text: str) -> list[str]:
    """
    given a text string, return list of cleaned words 
    punctuation removed 
    converted to lowercase
    """
    words = text.split()
    return [clean_word(w) for w in words if clean_word(w)]

def average_word_length(text: str) -> float:
    """
    returns the average length of the words in the text
    """
    clean_words = get_clean_words(text)
    if not clean_words:
        return 0.0
    total_length = sum(len(word) for word in clean_words)
    return total_length / len(clean_words)

def different_to_total(text: str) -> float:
    """
    given a text string 
    return ratio of different words to total words
    """
    clean_words = get_clean_words(text)
    total_words = len(clean_words)
    if total_words == 0:
        return 0.0
    different_words = len(set(clean_words))
    return different_words / total_words

def exactly_once_to_total(text: str) -> float:
    """
    returns the ratio of words that occur exactly once to the total number of words
    """
    clean_words = get_clean_words(text)
    total_words = len(clean_words)
    if total_words == 0:
        return 0.0
    word_counts = {}
    for word in clean_words:
        word_counts[word] = word_counts.get(word, 0) + 1
    exactly_once = sum(1 for count in word_counts.values() if count == 1)
    return exactly_once / total_words

def average_sentence_length(text: str) -> float:
    """
    returns the average length of sentences in the text
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return 0.0
    total_words = 0.0
    for sentence in sentences:
        words = sentence.split()
        total_words += len(words)
    return total_words / len(sentences)

def average_sentence_complexity(text: str) -> float:
    """
    given a text string 
    return average number of phrases per sentence
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return 0.0
    total_phrases = sum(len(split_into_phrases(sentence))
                        for sentence in sentences)
    return total_phrases / len(sentences)

def make_signature(text: str) -> dict[str, float]:
    """
    calculate a signature for the text consisting of:
    average_word_length 
    different_to_total 
    exactly_once_to_total 
    average_sentence_length 
    average_sentence_complexity    
    """

    return {
        "average_word_length": average_word_length(text),
        "different_to_total": different_to_total(text),
        "exactly_once_to_total": exactly_once_to_total(text),
        "average_sentence_length": average_sentence_length(text),
        "average_sentence_complexity": average_sentence_complexity(text),
    }

def calculate_distance(sig1: dict[str, float], sig2: dict[str, float]) -> float:
    """
    given two text signatures 
    return weighted distance between them
    """
    total = 0.0
    for feature, weight in weights.items():
        total += abs(sig1[feature] - sig2[feature]) * weight
    return total

def save_signatures(signatures: dict, path: Path) -> None:
    """
    given a dictionary of signatures and a path 
    save the signatures to that path as json
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(signatures, f, indent=2)

def load_signatures(path: Path) -> Optional[dict]:
    """
    given a path to a json file of signatures 
    return the signatures, or None if the file does not exist
    """
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def file_fingerprint(text_file: Path) -> dict[str, float]:
    """
    given a path to a text file 
    return its size and last-modified time 
    used to tell whether a cached signature is still good, or the 
    file has changed since the signature was cached
    """
    stat = text_file.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}

def _signature_task(text_file: Path) -> tuple[str, dict[str, float]]:
    """
    given a path to a text file 
    return a tuple of its name (without extension) and its signature 
    plain top-level function so it can run in a worker process
    """
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    return text_file.stem, make_signature(text)

def _guess_task(text_file: Path, known_signatures: dict[str, dict[str, float]]) -> tuple[str, Optional[str]]:
    """
    given a path to an unlabeled text file and known signatures 
    return a tuple of the file name and its guessed author 
    plain top-level function so it can run in a worker process
    """
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    unknown_sig = make_signature(text)
    return text_file.name, find_closest_signature(unknown_sig, known_signatures)

def make_known_signatures(labeled_texts_dir: Path, cache_path: Path) -> dict[str, dict[str, float]]:
    """
    given a directory of labeled texts and a path to a signature cache file 
    return dictionary mapping author name to signature

    each cache entry is stamped with the fingerprint of the labeled 
    file it came from 
    a labeled text whose fingerprint still matches the cache is loaded 
    straight from cache_path, not recomputed 
    a labeled text that is new, changed, or missing from the cache is 
    (re)computed in parallel, one process per file 
    editing a labeled text is picked up automatically on the next run
    """
    cache = load_signatures(cache_path) or {}

    text_files = sorted(labeled_texts_dir.glob("*.txt"))
    known_signatures = {}
    to_compute = []

    for text_file in text_files:
        author = text_file.stem
        fingerprint = file_fingerprint(text_file)
        cached_entry = cache.get(author)
        if cached_entry and cached_entry.get("fingerprint") == fingerprint:
            known_signatures[author] = cached_entry["signature"]
        else:
            to_compute.append(text_file)

    if to_compute:
        with ProcessPoolExecutor() as pool:
            for author, sig in pool.map(_signature_task, to_compute):
                known_signatures[author] = sig

    new_cache = {
        author: {
            "fingerprint": file_fingerprint(labeled_texts_dir / f"{author}.txt"),
            "signature": sig,
        }
        for author, sig in known_signatures.items()
    }
    save_signatures(new_cache, cache_path)

    return known_signatures

def find_closest_signature(unknown_sig: dict[str, float], known_sigs: dict[str, dict[str, float]]) -> Optional[str]:
    """
    given an unknown signature and dictionary of known signatures 
    return name of author with smallest distance
    """
    closest_author = None
    smallest_distance = float("inf")
    for author, known_sig in known_sigs.items():
        distance = calculate_distance(unknown_sig, known_sig)
        if distance < smallest_distance:
            smallest_distance = distance
            closest_author = author
    return closest_author

def guess_author(unlabeled_text_file: Path, known_signatures: dict[str, dict[str, float]]) -> Optional[str]:
    """
    given a file of unknown authorship and known signatures 
    return name of author whose signature is closest to the unknown text
    """
    with open(unlabeled_text_file, "r", encoding="utf-8") as f:
        unknown_text = f.read()

    unknown_sig = make_signature(unknown_text)
    return find_closest_signature(unknown_sig, known_signatures)

def choose_file(dir: Path) -> Path:
    """
    dir is a Path to a directory
    returns a Path to a file chosen by the user.
    """
    # get a list of the files in the directory
    texts = sorted(list(dir.iterdir()))
    # print a list of choices
    for i, file in enumerate(texts, start=1):
        print(f"{i}. {file.name}")
    # loop until we get an acceptable answer
    while True:
        try:
            choice = int(
                input(f"Please choose a text by number (1-{len(texts)}): "))
            if choice > 0:
                return texts[choice - 1]
        except (ValueError, IndexError):
            # something went wrong, try again
            pass

def main(labeled_texts_dir: Path, unlabeled_texts_dir: Path, cache_path: Path):
    """
    labeled_texts_dir is a Path to a directory of labeled texts
    unlabeled_texts_dir is a Path to a directory of unlabeled texts
    cache_path is a Path to a json file used to cache known signatures
    guesses the author of a text chosen by the user from the unlabeled directory.
    """
    try:
        known_signatures = make_known_signatures(labeled_texts_dir, cache_path)
        text = choose_file(unlabeled_texts_dir)
        author = guess_author(text, known_signatures)
        print("=" * 60)
        print(f"RESULT: {text.name} was written by {author}")
        print("=" * 60)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def _score_task(text_file: Path, known_signatures: dict[str, dict[str, float]]) -> tuple[str, dict[str, float]]:
    """
    given a path to an unlabeled text file and known signatures 
    return a tuple of the file name and a dict of distance to each author 
    plain top-level function so it can run in a worker process 
    used by --test-all to show WHY each guess was made, not just what
    """
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()
    unknown_sig = make_signature(text)
    distances = {
        author: calculate_distance(unknown_sig, known_sig)
        for author, known_sig in known_signatures.items()
    }
    return text_file.name, distances

def test_all_unknowns(labeled_texts_dir: Path, unlabeled_texts_dir: Path, cache_path: Path):
    """
    labeled_texts_dir is a Path to a directory of labeled texts
    unlabeled_texts_dir is a Path to a directory of unlabeled texts
    cache_path is a Path to a json file used to cache known signatures

    guesses the author of every text in the unlabeled directory 
    (one process per file) and prints the results 
    also prints the weighted distance to every author for every unknown, 
    so you can see WHY each guess was made, not just what
    """
    try:
        known_signatures = make_known_signatures(labeled_texts_dir, cache_path)

        text_files = sorted(unlabeled_texts_dir.glob("*.txt"))
        task = partial(_score_task, known_signatures=known_signatures)
        with ProcessPoolExecutor() as pool:
            results = dict(pool.map(task, text_files))

        authors = sorted(known_signatures.keys())
        col_width = max(len(a) for a in authors) + 2

        print("=" * 60)
        print("GUESSES:")
        for name in sorted(results):
            winner = min(results[name], key=results[name].get)
            print(f"  {name}: written by {winner}")
        print()
        print("DISTANCES (lower = closer, winner marked *):")
        header = " " * 18 + " ".join(a.ljust(col_width) for a in authors)
        print(header)
        for name in sorted(results):
            distances = results[name]
            winner = min(distances, key=distances.get)
            cells = []
            for a in authors:
                mark = "*" if a == winner else " "
                cells.append(f"{mark}{distances[a]:>6.2f}".ljust(col_width))
            print(f"  {name:<16}" + " ".join(cells))
        print("=" * 60)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def print_all_signatures(labeled_texts_dir: Path, unlabeled_texts_dir: Path, cache_path: Path):
    """
    labeled_texts_dir is a Path to a directory of labeled texts
    unlabeled_texts_dir is a Path to a directory of unlabeled texts
    cache_path is a Path to a json file used to cache known signatures

    prints every known and unknown signature 
    saves all of them together to signatures.json
    """
    try:
        known_signatures = make_known_signatures(labeled_texts_dir, cache_path)

        text_files = sorted(unlabeled_texts_dir.glob("*.txt"))
        with ProcessPoolExecutor() as pool:
            unknown_signatures = dict(pool.map(_signature_task, text_files))

        print("Known signatures:")
        for author, sig in known_signatures.items():
            print(f"  {author}: {sig}")
        print("Unknown signatures:")
        for name, sig in unknown_signatures.items():
            print(f"  {name}: {sig}")

        out_path = Path("signatures.json")
        save_signatures({"known": known_signatures, "unknown": unknown_signatures}, out_path)
        print(f"Saved all signatures to {out_path.resolve()}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    # check for required arguments and mode
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} texts_directory [--test-all | --print-signatures]", file=sys.stderr)
        print(f"  Default: Interactive mode (choose unknown file)", file=sys.stderr)
        print(f"  --test-all: Test all unknown files automatically", file=sys.stderr)
        print(f"  --print-signatures: Print all signatures and save to JSON", file=sys.stderr)
        sys.exit(2)
    
    texts_dir = Path(sys.argv[1])
    labeled_dir = texts_dir / "labeled"
    unlabeled_dir = texts_dir / "unlabeled"
    cache_path = labeled_dir / "known_signatures.json"
    
    # Check for optional mode flag
    mode = sys.argv[2] if len(sys.argv) > 2 else None
    
    if mode == "--test-all":
        test_all_unknowns(labeled_dir, unlabeled_dir, cache_path)
    elif mode == "--print-signatures":
        print_all_signatures(labeled_dir, unlabeled_dir, cache_path)
    else:
        # Default: interactive mode
        main(labeled_dir, unlabeled_dir, cache_path)