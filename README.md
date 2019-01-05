# MangaDex Ranker

**Update: [MangaDex has fixed their rating algorithm](https://mangadex.org/thread/49073). This script is now unmaintained.**

Script to rank manga on MangaDex. Uses a less naive rating algorithm.

```bash
# Set up a virtualenv first!
pip install -r requirements.txt
./mangadex.py -h
```

Example: Rank the top fantasy slice of life manga:

```bash
./mangadex.py --match-tags 'fantasy' 'slice of life'
```

Example: Rank the top fantasy manga which are not [isekai](https://en.wikipedia.org/wiki/Isekai):

```
./mangadex.py --match-tags fantasy --exclude-tags isekai
```

If you want to search using your account preferences, set the `MANGADEX_USERNAME` and `MANGADEX_PASSWORD` environment variables.
