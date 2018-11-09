#!/usr/bin/env python3

from bs4 import BeautifulSoup  # type: ignore
from dataclasses import dataclass
from typing import Dict, Optional
import bs4.element  # type: ignore
import math
import requests
import itertools


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


def query_mangadex(page: int = 1) -> str:
    # todo genre filters
    response = requests.get(
        'https://mangadex.org',
        params={
            's': '0',
            'page': 'search',  # page meaning "section of site"
            'p': str(page)  # page meaning "pagination"
        }
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
    # Awkwardly, the plural of manga is manga...
    collection: Dict[str, Manga] = {}

    for page in range(0, 15):
        mangadex_html = query_mangadex(page=page)
        mangadex_soup = BeautifulSoup(mangadex_html, 'html.parser')
        rows = mangadex_soup.body.find('div', id='content', role='main').find_all('div', class_='border-bottom')
        for row in rows:
            manga = __parse_manga_from_html(row)
            if manga:
                collection[manga.path] = manga

    top_manga = reversed(sorted(collection.values(), key=lambda m: m.adjusted_rating()))

    for i in range(0, 100):
        manga = next(top_manga)
        print(f'{i:>3}. {manga.name:48} {manga.adjusted_rating():.2f} ({manga.rating:.2f} x {manga.votes})')


if __name__ == '__main__':
    main()
