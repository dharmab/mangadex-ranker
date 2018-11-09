#!/usr/bin/env python3

from bs4 import BeautifulSoup  # type: ignore
from dataclasses import dataclass
from typing import List, Optional
import requests


@dataclass
class Manga:
    path: str
    name: str
    rating: float
    votes: int
    views: int
    follows: int


def query_mangadex() -> str:
    # todo genre filters
    response = requests.get('https://mangadex.org', params={'page': 'search'})
    response.raise_for_status()
    return response.text


def __parse_manga_from_html(row: str) -> Optional[Manga]:
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
    votes = int(rating_span['title'].split(' ')[0])

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
    mangadex_html = query_mangadex()
    mangadex_soup = BeautifulSoup(mangadex_html, 'html.parser')
    rows = mangadex_soup.body.find('div', id='content', role='main').find_all('div', class_='border-bottom')
    # Each row div contains two row divs.  The first div contains the original
    # language icon, title, author and follow button. The second contain the
    # stats.

    # Awkwardly, the plural of manga is manga...
    collection: List[Manga] = [__parse_manga_from_html(r) for r in rows]
    print(collection)


if __name__ == '__main__':
    main()
