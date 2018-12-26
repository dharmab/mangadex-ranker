#!/usr/bin/env python3

from bs4 import BeautifulSoup  # type: ignore
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Iterator, Optional
import argparse
import bs4.element  # type: ignore
import csv
import json
import math
import os
import requests
import sys
import yaml


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
        # 7.5 chosen because it is the median rating of relatively SFW data
        # queried in December 2018. (Mean is pretty close at 7.22)
        quantity_constant = -7.5 / math.log(0.5)
        adjusted_rating = (self.rating / 2.) + 5 * (1 - math.e ** ((-1 * self.votes) / quantity_constant))
        return round(adjusted_rating, 2)

    def url(self) -> str:
        return os.path.join('https://mangadex.org' + self.path)

    def __str__(self) -> str:
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'url': self.url(),
            'rating': self.rating,
            'adjusted_rating': self.adjusted_rating(),
            'votes': self.votes,
            'views': self.views,
            'follows': self.follows,
        }


def parse_args(tag_names: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Rank manga from MangaDex')
    parser.add_argument(
        '-l', '--list-tags',
        action='store_true',
        default=False,
        help='Print list of available tags and exit.'
    )
    parser.add_argument(
        '-m', '--match-tags',
        nargs='+',
        required=False,
        choices=tag_names,
        metavar='TAG',
        help='List of tags which manga must match. Omit to match any tags'
    )
    parser.add_argument(
        '-x', '--exclude-tags',
        nargs='+',
        required=False,
        choices=tag_names,
        metavar='TAG',
        help='List of tags which manga must not match. Omit to disable tag exclusion'
    )
    parser.add_argument(
        '-p', '--pages',
        default='10',
        required=False,
        metavar='N',
        help='Number of search result pages to parse'
    )
    parser.add_argument(
        '--minimum-rating',
        default='8.00',
        required=False,
        metavar='RATING',
        help='Minimum adjusted rating (0.0 to 10.0). Manga below this rating are not listed'
    )
    parser.add_argument(
        '-f', '--format',
        default='wide',
        required=False,
        choices=['simple', 'wide', 'json', 'yaml', 'csv'],
        help='Output format'
    )

    return parser.parse_args()


def __mangadex_search_url() -> str:
    return 'https://mangadex.org/search'


def get_mangadex_tags(*, session: requests.Session) -> Dict[str, str]:
    """
    Dynamically build the list of MangaDex tags.

    :param session: A HTTP session for MangaDex. May be authenticated or
    unauthenticated.
    :return: A dictionary where keys are lowercase tag names
    and values are numeric tags.
    """
    response = session.get(__mangadex_search_url())
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')

    tags: Dict[str, str] = {}
    option_groups = soup.body.find('div', class_='genres-filter-wrapper').find_all('optgroup')
    for group in option_groups:
        options = group.find_all('option')
        for option in options:
            tags[option.string.lower()] = option['value']
    return tags


def __search_mangadex(*, session: requests.Session, page: int = 1, included_tags: Optional[Set[str]] = None, excluded_tags: Optional[Set[str]] = None) -> str:
    """
    Search MangaDex and return the HTML response from the search page.

    :param session: A HTTP session for MangaDex. May be authenticated or
    unauthenticated.
    :param page: The page of search results to query.
    :param included_tags: The numeric values of tags to match on (include). If
    None, all tags will be included
    :param excluded_tags: The numeric values of tags to exclude. If None, no
    tags will be excluded
    :return: The HTML body of the MangaDex search page.
    """
    params: Dict[str, str] = {
        's': '7',  # sort method; 7 sorts by views descending
        'p': str(page)  # pagination
    }

    def format_tag_list(c: Set[str]) -> str:
        return ','.join(sorted(c))

    if included_tags:
        params['tags_inc'] = format_tag_list(included_tags)
    if excluded_tags:
        params['tags_exc'] = format_tag_list(excluded_tags)

    response = session.get(__mangadex_search_url(), params=params)
    response.raise_for_status()
    return response.text


def __parse_manga_from_html(row: bs4.element.Tag) -> Optional[Manga]:
    """
    Helper function for parsing manga metadata from MangaDex HTML results.
    """
    title = row.find('a', class_='manga_title').text
    if not title:
        return None

    # Clean up data
    for s in ['[Official Colored]', '(Anthology)', '(Doujinshi)', '(Web Comic)', '(Webcomic)']:
        if s in title:
            title = title.rstrip(s)
        if s.lower() in title:
            title = title.rstrip(s.lower())
    title = title.strip()

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


def get_manga(*, session: requests.Session, number_of_pages: int, included_tags: Optional[Set[str]] = None, excluded_tags: Optional[Set[str]] = None) -> Iterator[Manga]:
    """
    Query manga metadata from MangaDex.

    :param session: A HTTP session for MangaDex. May be authenticated or
    unauthenticated.
    :param number_of_pages: Number of pages of search results to return.
    :param included_tags: The numeric values of tags to match on (include). If
    None, all tags will be included
    :param excluded_tags: The numeric values of tags to exclude. If None, no
    tags will be excluded

    :return: Iterator of Manga results.
    """
    # Awkwardly, the plural of manga is manga...
    collection: Dict[str, Manga] = {}

    # Unfortunately queries cannot be multithreaded due to rate limiting
    for page in range(0, number_of_pages):
        mangadex_html = __search_mangadex(
            session=session,
            page=page,
            included_tags=included_tags,
            excluded_tags=excluded_tags
        )
        mangadex_soup = BeautifulSoup(mangadex_html, 'html.parser')
        rows = mangadex_soup.body.find('div', id='content', role='main').find_all('div', class_='border-bottom')

        # Stop searching if no further results are found
        if not rows:
            break

        for row in rows:
            manga = __parse_manga_from_html(row)
            # Exclude https://mangadex.org/title/47/test
            if manga and manga.name != 'Test':
                collection[manga.path] = manga

    yield from collection.values()


def login(username: Optional[str] = None, password: Optional[str] = None) -> requests.Session:
    """
    Start an HTTP session for MangaDex. Username and password are optional and
    only needed if the user wants to use their account settings to customize
    their search results.

    :param username: MangaDex username
    :param password: MangaDex password
    :return: An HTTP session which may or may not be authenticated.
    """
    session = requests.Session()
    if username and password:
        # cookie is implicitly saved in session
        session.post(
            'https://mangadex.org/ajax/actions.ajax.php',
            params={'function': 'login'},
            payload={
                'login_username': username,
                'login_password': password
            }
        )
    return session


def main() -> None:
    # Start a MangaDex HTTP session
    session = login(
        username=os.getenv('MANGADEX_USERNAME', None),
        password=os.getenv('MANGADEX_PASSWORD', None)
    )

    # Dynamically query available tags
    tags = get_mangadex_tags(session=session)

    # Parse CLI options
    options = parse_args(tag_names=list(tags.keys()))

    def select_tags(o: Optional[List[str]]) -> Optional[Set[str]]:
        return {tags[s.lower()] for s in o} if o else None
    included_tags = select_tags(options.match_tags)
    excluded_tags = select_tags(options.exclude_tags)

    if options.list_tags:
        for tag in sorted(tags.keys()):
            print(tag)
        sys.exit(0)

    # Query for Manga metadata
    queried_manga = get_manga(
        session=session,
        number_of_pages=int(options.pages),
        included_tags=included_tags,
        excluded_tags=excluded_tags
    )

    # Rank manga by rating descending
    ranked_manga = filter(
        lambda m: m.adjusted_rating() > float(options.minimum_rating),
        reversed(
            sorted(
                queried_manga,
                key=lambda m: m.adjusted_rating()
            )
        )
    )

    # Print results
    if options.format == 'simple':
        for manga in ranked_manga:
            print(f'{manga.name:72}')
    elif options.format == 'wide':
        for i, manga in enumerate(ranked_manga):
            print(f'{i+1:>3}. {manga.name:72} {manga.adjusted_rating():.2f} ({manga.rating:.2f} x {manga.votes})')
            i += 1
    elif options.format == 'json':
        print(json.dumps([m.to_dict() for m in ranked_manga]))
    elif options.format == 'yaml':
        print(yaml.dump([m.to_dict() for m in ranked_manga]))
    elif options.format == 'csv':
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=[
                'name',
                'url',
                'rating',
                'adjusted_rating',
                'votes',
                'views',
                'follows'
            ]
        )
        writer.writeheader()
        for m in ranked_manga:
            writer.writerow(m.to_dict())


if __name__ == '__main__':
    main()
