from typing import Dict, Tuple, List
from collections import namedtuple

StringSequence = List[str]
DictionaryOverride = namedtuple("DictionaryOverride", "meanings on kun", defaults=(None, None, None))

# Meaning, On, Kun
overrides: Dict[str, DictionaryOverride]
overrides = {
    "本": DictionaryOverride(["book"]),
    "年": DictionaryOverride(["year"]),
    "日": DictionaryOverride(["day", "japan"]),
    "見": DictionaryOverride(["see", "show"]),
    "行": DictionaryOverride(["going", "journey"]),
}