# MangaDex Ranker

Script to rank manga on MangaDex. Uses a less naive rating algorithm.

```bash
# Set up a virtualenv first!
pip install -r requirements.txt
./mangadex.py -h
```

Example: Rank the top fantasy slice of life manga:

```bash
./mangadex.py --match-genres 'fantasy' 'slice of life'
```
