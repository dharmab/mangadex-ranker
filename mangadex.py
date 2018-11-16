#!/usr/bin/env python3

from bs4 import BeautifulSoup  # type: ignore
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urljoin
import argparse
import bs4.element  # type: ignore
import enum
import math
import os
import requests


class Genre(enum.Enum):
    FOUR_KOMA = 1
    ACTION = 2
    ADVENTURE = 3
    AWARD_WINNING = 4
    COMEDY = 5
    COOKING = 6
    DOUJINSHI = 7
    DRAMA = 8
    ECCHI = 9
    FANTASY = 10
    GENDER_BENDER = 11
    HAREM = 12
    HISTORICAL = 13
    HORROR = 14
    JOSEI = 15
    MARTIAL_ARTS = 16
    MECHA = 17
    MEDICAL = 18
    MUSIC = 19
    MYSTERY = 20
    ONESHOT = 21
    PSYCHOLOGICAL = 22
    ROMANCE = 23
    SCHOOL_LIFE = 24
    SCI_FI = 25
    SEINEN = 26
    SHOUJO = 27
    SHOUJO_AI = 28
    SHOUNEN = 29
    SHOUNEN_AI = 30
    SLICE_OF_LIFE = 31
    SMUT = 32
    SPORTS = 33
    SUPERNATURAL = 34
    TRAGEDY = 35
    WEBTOON = 36
    YAOI = 37
    YURI = 38
    # skipping "no chapters"
    GAME = 40
    ISEKAI = 41

    @staticmethod
    def from_str(s: str):
        s = s.replace(' ', '_').upper()
        try:
            return Genre[s]
        except ValueError:
            return {
                '4-KOMA': Genre.FOUR_KOMA,
                'SCI-FI': Genre.SCI_FI
            }[s]

    @staticmethod
    def choices() -> List[str]:
        names = [n.replace('_', ' ').lower() for n in Genre.__members__.keys()]
        for i, name in enumerate(names):
            if name == 'four koma':
                names[i] = '4-koma'
            if name == 'sci fi':
                names[i] = 'sci-fi'
        return names


class Sorting(enum.Enum):
    TITLE_ASC = 2
    TITLE_DESC = 3
    COMMENTS_ASC = 4
    COMMENTS_DESC = 5
    RATING_ASC = 6
    RATING_DESC = 7
    VIEWS_ASC = 8
    VIEWS_DESC = 9
    FOLLLOWS_ASC = 10
    FOLLLOWS_DESC = 11
    LAST_UPDATE_ASC = 12
    LAST_UPDATE_DESC = 13


@dataclass
class Manga:
    path: str
    name: str
    rating: float
    votes: int
    views: int
    follows: int

    def adjusted_rating(self) -> float:
        # Bravely stolen from https://math.stackexchange.com/a/942965
        # Considering 7.5 to be an arbitrary "moderate" rating
        quantity_constant = -7.5 / math.log(0.5)
        adjusted_rating = (self.rating / 2.) + 5 * (1 - math.e ** ((-1 * self.votes) / quantity_constant))
        return round(adjusted_rating, 2)

    def __str__(self):
        return self.title


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Rank manga from MangaDex')
    parser.add_argument(
        '-m', '--match-genres',
        nargs='+',
        required=False,
        choices=Genre.choices(),
        metavar='GENRE',
        help='List of genres which manga must match. Omit to match any genres'
    )
    parser.add_argument(
        '-p', '--pages',
        default='10',
        required=False,
        help='Number of search result pages to parse'
    )
    parser.add_argument(
        '--minimum-rating',
        default='8.00',
        required=False,
        help='Minimum adjusted rating. Manga below this rating are not listed'
    )

    return parser.parse_args()


def query_mangadex(*, session: requests.Session, page: int = 1, match_genres: Optional[List[Genre]] = None) -> str:
    params: Dict[str, str] = {
        's': str(Sorting.VIEWS_DESC),  # sort method
        'page': 'search',  # page meaning "section of site"
        'p': str(page)  # page meaning "pagination"
    }

    if match_genres:
        params['genres_inc'] = ','.join(sorted([str(e.value) for e in match_genres]))

    response = session.get(
        'https://mangadex.org',
        params=params
    )
    response.raise_for_status()
    return response.text


def __parse_manga_from_html(row: bs4.element.Tag) -> Optional[Manga]:
    title = row.find('a', class_='manga_title').text
    if not title:
        return None

    path = row.find('a')['href']

    # The Rating span is for the user's rating.
    # The community rating is a few elements over.
    rating_span = row.find('span', title='Rating').next_element.next_element.next_element.next_element.next_element
    rating = float(rating_span.text)

    def parse_int(s: str) -> int:
        return int(s.strip().replace(',', ''))

    # Vote count is in format "n Votes"
    votes = parse_int(rating_span['title'].split(' ')[0])
    follows = parse_int(row.find('span', title='Follows').next_element)
    views = parse_int(row.find('span', title='Views').next_element)

    return Manga(
        path=path,
        name=title,
        views=views,
        follows=follows,
        rating=rating,
        votes=votes
    )


def main():
    options = parse_args()

    # Awkwardly, the plural of manga is manga...
    collection: Dict[str, Manga] = {}

    if options.match_genres:
        match_genres = [Genre.from_str(s) for s in options.match_genres]
    else:
        match_genres = None

    session = requests.Session()
    username = os.getenv('MANGADEX_USERNAME', None)
    password = os.getenv('MANGADEX_PASSWORD', None)

    if username and password:
        # cookie is implicitly saved in session
        session.post(
            urljoin('https://mangadex.org/ajax/actions.ajax.php'),
            params={'function': 'login'},
            payload={
                'login_username': username,
                'login_password': password
            }
        )

    # Unfortunately queries cannot be multithreaded due to rate limiting
    for page in range(0, int(options.pages)):
        mangadex_html = query_mangadex(session=session, page=page, match_genres=match_genres)
        mangadex_soup = BeautifulSoup(mangadex_html, 'html.parser')
        rows = mangadex_soup.body.find('div', id='content', role='main').find_all('div', class_='border-bottom')
        for row in rows:
            manga = __parse_manga_from_html(row)
            if manga:
                collection[manga.path] = manga

    top_manga = reversed(sorted(collection.values(), key=lambda m: m.adjusted_rating()))

    for i, manga in enumerate(top_manga):
        if manga.adjusted_rating() < float(options.minimum_rating):
            break
        print(f'{i:>3}. {manga.name:72} {manga.adjusted_rating():.2f} ({manga.rating:.2f} x {manga.votes})')
        i += 1


if __name__ == '__main__':
    main()
