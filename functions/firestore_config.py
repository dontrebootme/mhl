"""Firestore configuration and collection namespacing."""

PREFIX = "mhlv2_"


class COLS:
    """Collection names with namespacing prefix applied."""

    GAMES = f"{PREFIX}games"
    STANDINGS = f"{PREFIX}standings"
    SEASONS = f"{PREFIX}seasons"
    DIVISIONS = f"{PREFIX}divisions"
    TEAMS = f"{PREFIX}teams"
    METADATA = f"{PREFIX}metadata"
